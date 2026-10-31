import os
import shutil
import asyncio
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, List

import json
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import init_settings
from app.database import get_db, init_db, SessionLocal
from app.models import User, Conversation, Message
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.rag_engine import rag_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite tables and AI models once on server startup
    init_db()
    init_settings()
    yield

app = FastAPI(
    title="LlamaReader AI - Conversational Document RAG",
    description="ChatGPT-style multi-turn RAG interface with persistent user accounts, chat history, and document indexing",
    lifespan=lifespan
)

@app.middleware("http")
async def add_cache_control_header(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ----------------- Request / Response Schemas -----------------

class AuthRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)

class IndexUrlRequest(BaseModel):
    url: str

class QueryRequest(BaseModel):
    question: str
    stream: Optional[bool] = True

class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)

# ----------------- Auth Endpoints -----------------

@app.post("/api/auth/register")
async def register(req: AuthRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    clean_username = req.username.strip()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username cannot be blank.")

    existing = db.query(User).filter(User.username == clean_username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists. Please choose another or log in.")

    hashed_pw = hash_password(req.password)
    user = User(username=clean_username, hashed_password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": user.username, "user_id": user.id})
    return {
        "status": "success",
        "message": "Account created successfully.",
        "token": token,
        "username": user.username
    }

@app.post("/api/auth/login")
async def login(req: AuthRequest, db: Session = Depends(get_db)):
    """Authenticate existing user credentials."""
    clean_username = req.username.strip()
    user = db.query(User).filter(User.username == clean_username).first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    token = create_access_token(data={"sub": user.username, "user_id": user.id})
    return {
        "status": "success",
        "token": token,
        "username": user.username
    }

@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Check current authentication status and return user details."""
    return {
        "id": current_user.id,
        "username": current_user.username
    }

# ----------------- Conversation Endpoints -----------------

@app.get("/api/conversations")
async def list_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all conversations for the authenticated user."""
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )

    return [
        {
            "id": c.id,
            "title": c.title,
            "source_type": c.source_type,
            "source_name": c.source_name,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            "message_count": len(c.messages)
        }
        for c in convs
    ]

@app.post("/api/conversations")
async def create_conversation(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new conversation session."""
    conv = Conversation(user_id=current_user.id, title="New Chat")
    db.add(conv)
    db.commit()
    db.refresh(conv)

    return {
        "id": conv.id,
        "title": conv.title,
        "source_type": conv.source_type,
        "source_name": conv.source_name,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "messages": []
    }

@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch conversation details and its complete message history."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return {
        "id": conv.id,
        "title": conv.title,
        "source_type": conv.source_type,
        "source_name": conv.source_name,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "has_index": rag_engine.has_persisted_index(conv.id),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            }
            for m in conv.messages
        ]
    }

@app.patch("/api/conversations/{conv_id}")
async def rename_conversation(
    conv_id: str,
    req: RenameConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Rename a conversation."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conv.title = req.title.strip()
    db.commit()
    return {"status": "success", "id": conv.id, "title": conv.title}

@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a conversation, its messages, and its persistent vector store."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # Remove vector index from disk
    rag_engine.delete_conversation_index(conv.id)

    db.delete(conv)
    db.commit()
    return {"status": "success", "message": "Conversation deleted successfully."}

# ----------------- Document Ingestion per Conversation -----------------

@app.post("/api/conversations/{conv_id}/index-url")
async def index_conversation_url(
    conv_id: str,
    req: IndexUrlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Index a webpage URL into this conversation's vector index."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    url = req.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    success, message = rag_engine.index_url(conv.id, url)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    conv.source_type = "url"
    conv.source_name = url
    if conv.title == "New Chat":
        # Create a clean title from the URL
        url_part = url.split("://")[-1].split("?")[0].rstrip("/")
        conv.title = url_part[:40]

    conv.updated_at = datetime.utcnow()
    db.commit()

    return {
        "status": "success",
        "message": message,
        "source_type": "url",
        "source_name": url,
        "title": conv.title
    }

@app.post("/api/conversations/{conv_id}/upload")
async def upload_conversation_file(
    conv_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and index a PDF or TXT document into this conversation's vector index."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".txt", ".md", ".log", ".csv", ".json"]:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a PDF or TXT file.")

    temp_dir = Path("temp_uploads")
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / f"upload_{os.urandom(6).hex()}{ext}"

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        success, message = rag_engine.index_file(conv.id, str(temp_path), filename=file.filename)
        if not success:
            raise HTTPException(status_code=400, detail=message)

        conv.source_type = "file"
        conv.source_name = file.filename
        if conv.title == "New Chat":
            conv.title = file.filename[:40]

        conv.updated_at = datetime.utcnow()
        db.commit()

        return {
            "status": "success",
            "message": message,
            "source_type": "file",
            "source_name": file.filename,
            "title": conv.title
        }
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

# ----------------- Query / Chat Endpoint -----------------

@app.post("/api/conversations/{conv_id}/query")
async def query_conversation(
    conv_id: str,
    req: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Query this conversation with conversational memory, RAG context, and real-time streaming."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # 1. Save user question
    user_msg = Message(conversation_id=conv.id, role="user", content=question)
    db.add(user_msg)
    db.commit()

    # 2. Check if streaming requested (default True for modern ChatGPT experience)
    if req.stream:
        try:
            token_gen = rag_engine.stream_chat(conv.id, question, db)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start stream: {str(e)}")

        async def sse_generator():
            accumulated = []
            try:
                for token in token_gen:
                    accumulated.append(token)
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    await asyncio.sleep(0)
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                full_text = "".join(accumulated).strip()
                if full_text:
                    try:
                        with SessionLocal() as save_db:
                            asst_msg = Message(conversation_id=conv.id, role="assistant", content=full_text)
                            save_db.add(asst_msg)
                            c = save_db.query(Conversation).filter(Conversation.id == conv.id).first()
                            if c:
                                if c.title == "New Chat":
                                    c.title = question[:35] + ("..." if len(question) > 35 else "")
                                c.updated_at = datetime.utcnow()
                            save_db.commit()
                    except Exception as err:
                        print(f"Error persisting message: {err}")
                yield f"data: {json.dumps({'done': True, 'title': conv.title})}\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    # Fallback non-streaming mode
    try:
        answer = rag_engine.chat(conv.id, question, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    assistant_msg = Message(conversation_id=conv.id, role="assistant", content=answer)
    db.add(assistant_msg)
    conv.updated_at = datetime.utcnow()
    if conv.title == "New Chat":
        conv.title = question[:35] + ("..." if len(question) > 35 else "")
    db.commit()

    return {
        "status": "success",
        "answer": answer,
        "title": conv.title
    }

# ----------------- Static SPA Frontend -----------------

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def serve_index():
    """Serve the single-page application frontend."""
    return FileResponse(STATIC_DIR / "index.html")

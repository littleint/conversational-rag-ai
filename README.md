# 🦙 LlamaReader AI — ChatGPT for Documents & Webpages

A full-featured, private, multi-user **ChatGPT-style Conversational RAG Application** powered by **LlamaIndex**, **Groq LLM (`gpt-oss-120b`)**, **FastAPI**, and **SQLite**.

Upload PDFs, text documents, or paste any public webpage URL to chat with them in real time with word-by-word streaming, persistent conversation history, and a modern collapsible sidebar.

---

## 🌟 Key Features

- **💬 ChatGPT-Style Interface**:
  - Sleek modern dark workspace with collapsible left sidebar.
  - Chronological conversation history categorized into **Today**, **Previous 7 Days**, and **Older**.
  - **"+ New Chat"** button with inline conversation renaming and deletion.
  - Clean center prompt area: *"What can I help with?"* and quick-start action pills.

- **🔒 User Authentication & Privacy (Register Once, Login Anytime)**:
  - Local **SQLite (`llamareader.db`)** database with salted `bcrypt` password hashing.
  - Persistent JWT session tokens stored in the browser — users stay logged in across page refreshes and server restarts.
  - **Multi-Tenant Isolation**: Each user can only view, query, and manage their own private chats and documents.
  - **⚡ Quick Demo Login**: One-click instant login button for immediate evaluation without typing credentials.

- **⚡ Real-Time Streaming & "Stop Generating" (⏹️)**:
  - **Word-by-Word Token Streaming**: Answers stream in real-time via Server-Sent Events (SSE).
  - **Instant Cancellation**: The Send button transforms into a square **Stop Button (⏹️)** with an `AbortController` to halt generation instantly if a question is off-track.

- **📚 Multi-Document RAG**:
  - **Webpages**: Scrape and index articles, blogs, and documentation URLs using `requests` and `html2text`.
  - **Files**: Drag-and-drop or upload PDF, TXT, Markdown, CSV, and log files.

- **☁️ Cloud-Native Dual Memory (Zero Cost & Sub-10ms Speed)**:
  - **Short-Term Memory**: **Upstash Redis** maintains low-latency active conversational context (<5ms) with auto-expiring TTLs and automatic SQLite hydration.
  - **Long-Term Memory (Semantic)**: **Qdrant Cloud** stores vectorized document and webpage embeddings with payload-level multi-tenant isolation (`conversation_id`).
  - **Long-Term Archive**: Local **SQLite (`llamareader.db`)** manages permanent user accounts and historical chat logs.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend API** | FastAPI, Uvicorn, Pydantic, Python-Multipart |
| **AI / RAG Framework** | LlamaIndex (`VectorStoreIndex`, `ChatMemoryBuffer`, `SimpleChatEngine`, `QdrantVectorStore`) |
| **LLM & Embeddings** | **Groq Cloud API** (`openai/gpt-oss-120b`), **HuggingFace** (`BAAI/bge-small-en-v1.5`) |
| **Short-Term Memory** | **Upstash Redis** (Serverless REST Key-Value) |
| **Long-Term Vector Memory** | **Qdrant Cloud** (Managed In-Memory HNSW) |
| **Database & Auth** | SQLite, SQLAlchemy ORM, Bcrypt, PyJWT |
| **Document Parsers** | PyPDF, HTML2Text, Requests |
| **Frontend** | Vanilla HTML5, Modern CSS3 (ChatGPT Dark Theme), JavaScript (ES6+), Marked.js, Highlight.js |

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/littleint/chat-with-webpage.git
cd chat-with-webpage
```

### 2. Create and activate a virtual environment
```powershell
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root:
```env
GROQ_API_KEY=your_groq_api_key_here
QDRANT_URL=https://xxxx.cloud.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key_here
UPSTASH_REDIS_REST_URL=https://xxxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=your_upstash_token_here
```
*(All three services offer permanent free tiers with zero credit card required).*

### 5. Launch the application
```powershell
python run.py
```

The web app will be available at:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 📂 Project Structure

```text
llamaindex_project/
├── app/
│   ├── auth.py              # Password hashing (bcrypt) & JWT token handling
│   ├── config.py            # Groq LLM & HuggingFace embedding settings
│   ├── database.py          # SQLite connection and session management
│   ├── loaders.py           # Web scraping & PDF/TXT document ingestion
│   ├── main.py              # FastAPI REST endpoints & SSE streaming
│   ├── models.py            # SQLAlchemy models (User, Conversation, Message)
│   └── rag_engine.py        # Vector index management, persistence & memory
├── static/
│   ├── css/
│   │   └── style.css        # ChatGPT dark theme stylesheet
│   ├── js/
│   │   └── app.js           # Client-side state, streaming reader & UI logic
│   └── index.html           # Single-page application HTML layout
├── storage/                 # Local vector indices (ignored by Git)
│   └── indices/
│       └── {conv_id}/       # On-disk vector store and docstore JSON files
├── llamareader.db           # Local SQLite database (ignored by Git)
├── temp_uploads/            # Temporary upload buffer (ignored by Git)
├── .env                     # API keys (ignored by Git)
├── .gitignore               # Excludes secrets, databases & vector storage
├── requirements.txt         # Project Python dependencies
├── run.py                   # Application startup script
└── README.md                # Project documentation
```

---

## 🔌 API Reference

### Authentication
- `POST /api/auth/register` — Create a new account with hashed password.
- `POST /api/auth/login` — Authenticate credentials and return a signed JWT token.
- `GET /api/auth/me` — Verify current user session.

### Conversations
- `GET /api/conversations` — List all conversations for the authenticated user.
- `POST /api/conversations` — Create a new conversation session.
- `GET /api/conversations/{id}` — Fetch conversation details, attached document info, and full message history.
- `PATCH /api/conversations/{id}` — Rename a conversation title.
- `DELETE /api/conversations/{id}` — Delete a conversation, its messages, and its persistent vector index on disk.

### Document Ingestion & Querying
- `POST /api/conversations/{id}/index-url` — Scrape and index a webpage URL for this chat.
- `POST /api/conversations/{id}/upload` — Upload and index a PDF or TXT file for this chat.
- `POST /api/conversations/{id}/query` — Stream real-time answers (`text/event-stream`) with multi-turn memory.

---

## 🔒 Security & Privacy

- **100% Local Data**: All chat messages, user records, and vector indices stay on your machine in `llamareader.db` and `storage/indices/`.
- **Git Protection**: `.gitignore` is strictly configured to prevent accidentally committing `.env` API keys, database files, or document stores to GitHub.
- **Passwords**: Passwords are cryptographically salted and hashed using `bcrypt` before storage.

---

## 📄 License

This project is licensed under the MIT License.

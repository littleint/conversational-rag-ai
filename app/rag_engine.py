import os
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session

from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.chat_engine import SimpleChatEngine
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client.http import models

from app.config import (
    get_qdrant_client,
    QDRANT_COLLECTION,
    UPSTASH_REDIS_REST_URL,
    UPSTASH_REDIS_REST_TOKEN
)
from app.upstash_chat_store import UpstashChatStore
from app.loaders import load_web_url, load_pdf_file, load_txt_file
from app.models import Message


class RAGEngineManager:
    """
    Manages cloud-native document vectorization (Qdrant Cloud)
    and ultra-fast short-term conversational working memory (Upstash Redis).
    """

    def __init__(self):
        # Qdrant Cloud Vector Store
        self.qdrant_client = get_qdrant_client()
        self.vector_store = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=QDRANT_COLLECTION
        )
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

        # Upstash Redis Short-Term Chat Store
        if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
            self.chat_store = UpstashChatStore(
                url=UPSTASH_REDIS_REST_URL,
                token=UPSTASH_REDIS_REST_TOKEN,
                ttl=2592000  # 30 days retention
            )
        else:
            self.chat_store = None

    @property
    def index(self) -> VectorStoreIndex:
        """Lazily load VectorStoreIndex bound to current Settings.embed_model."""
        return VectorStoreIndex.from_vector_store(
            self.vector_store,
            embed_model=Settings.embed_model
        )

    def has_persisted_index(self, conversation_id: str) -> bool:
        """Check if any document vector points exist in Qdrant for this conversation."""
        try:
            count_result = self.qdrant_client.count(
                collection_name=QDRANT_COLLECTION,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="conversation_id",
                            match=models.MatchValue(value=conversation_id)
                        )
                    ]
                )
            )
            return count_result.count > 0
        except Exception as e:
            print(f"Error checking Qdrant index for conversation {conversation_id}: {e}")
            return False

    def delete_conversation_points(self, conversation_id: str):
        """Remove all vector chunks for a specific conversation from Qdrant Cloud."""
        try:
            self.qdrant_client.delete(
                collection_name=QDRANT_COLLECTION,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="conversation_id",
                                match=models.MatchValue(value=conversation_id)
                            )
                        ]
                    )
                )
            )
        except Exception as e:
            print(f"Warning: Failed to delete Qdrant points for {conversation_id}: {e}")

    def delete_conversation_index(self, conversation_id: str):
        """Clean up both Qdrant Cloud vector chunks and Upstash Redis short-term memory."""
        self.delete_conversation_points(conversation_id)
        if self.chat_store:
            try:
                self.chat_store.delete_messages(conversation_id)
            except Exception as e:
                print(f"Warning: Failed to delete Upstash chat memory for {conversation_id}: {e}")

    def index_url(self, conversation_id: str, url: str) -> Tuple[bool, str]:
        """Scrape webpage, vectorize chunks, and push directly to Qdrant Cloud."""
        try:
            docs = load_web_url(url)
            # Tag each document with conversation_id for multi-tenant isolation
            for doc in docs:
                doc.metadata["conversation_id"] = conversation_id

            # Clean previous points for this conversation if replacing document
            self.delete_conversation_points(conversation_id)

            print(f"Indexing URL to Qdrant Cloud for conv {conversation_id}: {url} ({len(docs)} sections)...", flush=True)
            VectorStoreIndex.from_documents(
                docs,
                storage_context=self.storage_context,
                embed_model=Settings.embed_model
            )
            return True, f"Successfully indexed '{url}' to Qdrant Cloud ({len(docs)} sections loaded)."
        except Exception as e:
            return False, f"Failed to index URL: {str(e)}"

    def index_file(self, conversation_id: str, temp_file_path: str, filename: str) -> Tuple[bool, str]:
        """Parse PDF/TXT, vectorize chunks, and push directly to Qdrant Cloud."""
        try:
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".pdf":
                docs = load_pdf_file(temp_file_path, filename=filename)
            elif ext in [".txt", ".md", ".log", ".csv", ".json"]:
                docs = load_txt_file(temp_file_path, filename=filename)
            else:
                return False, f"Unsupported file type: {ext}. Please upload a PDF or TXT file."

            # Tag each document with conversation_id for multi-tenant isolation
            for doc in docs:
                doc.metadata["conversation_id"] = conversation_id

            # Clean previous points for this conversation if replacing document
            self.delete_conversation_points(conversation_id)

            print(f"Indexing file to Qdrant Cloud for conv {conversation_id}: {filename} ({len(docs)} chunks)...", flush=True)
            VectorStoreIndex.from_documents(
                docs,
                storage_context=self.storage_context,
                embed_model=Settings.embed_model
            )
            return True, f"Successfully indexed '{filename}' to Qdrant Cloud ({len(docs)} sections loaded)."
        except Exception as e:
            return False, f"Failed to index file: {str(e)}"

    def _get_chat_memory(self, conversation_id: str, db: Session, current_question: str = "") -> ChatMemoryBuffer:
        """
        Fetch short-term conversational context from Upstash Redis (<5ms).
        If Redis is cold/empty, automatically hydrates from SQLite.
        """
        if self.chat_store:
            existing = self.chat_store.get_messages(conversation_id)
            if not existing:
                # Hydrate from SQLite
                past_messages = (
                    db.query(Message)
                    .filter(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                    .all()
                )
                # If current_question was already saved to SQLite before calling this, exclude it
                # so chat_engine doesn't receive it twice in memory
                if current_question and past_messages and past_messages[-1].role == "user" and past_messages[-1].content == current_question:
                    past_messages = past_messages[:-1]

                chat_history = []
                for msg in past_messages:
                    role = MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT
                    chat_history.append(ChatMessage(role=role, content=msg.content))

                if chat_history:
                    self.chat_store.set_messages(conversation_id, chat_history)

            return ChatMemoryBuffer.from_defaults(
                chat_store=self.chat_store,
                chat_store_key=conversation_id,
                token_limit=3500
            )

        # Fallback if Redis is not configured
        past_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        if current_question and past_messages and past_messages[-1].role == "user" and past_messages[-1].content == current_question:
            past_messages = past_messages[:-1]

        chat_history = []
        for msg in past_messages:
            role = MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT
            chat_history.append(ChatMessage(role=role, content=msg.content))
        return ChatMemoryBuffer.from_defaults(chat_history=chat_history, token_limit=3500)

    def chat(self, conversation_id: str, question: str, db: Session) -> str:
        """Synchronous query with conversational memory and Qdrant RAG."""
        memory = self._get_chat_memory(conversation_id, db, current_question=question)
        has_docs = self.has_persisted_index(conversation_id)

        if has_docs:
            filters = MetadataFilters(
                filters=[ExactMatchFilter(key="conversation_id", value=conversation_id)]
            )
            chat_engine = self.index.as_chat_engine(
                chat_mode="condense_plus_context",
                llm=Settings.llm,
                memory=memory,
                filters=filters,
                verbose=False
            )
            response = chat_engine.chat(question)
            return str(response)
        else:
            chat_engine = SimpleChatEngine.from_defaults(llm=Settings.llm, memory=memory)
            response = chat_engine.chat(question)
            return str(response)

    def stream_chat(self, conversation_id: str, question: str, db: Session):
        """Real-time streaming query generator with Upstash short-term memory & Qdrant RAG."""
        memory = self._get_chat_memory(conversation_id, db, current_question=question)
        has_docs = self.has_persisted_index(conversation_id)

        if has_docs:
            filters = MetadataFilters(
                filters=[ExactMatchFilter(key="conversation_id", value=conversation_id)]
            )
            chat_engine = self.index.as_chat_engine(
                chat_mode="condense_plus_context",
                llm=Settings.llm,
                memory=memory,
                filters=filters,
                verbose=False
            )
            streaming_response = chat_engine.stream_chat(question)
            return streaming_response.response_gen
        else:
            chat_engine = SimpleChatEngine.from_defaults(llm=Settings.llm, memory=memory)
            streaming_response = chat_engine.stream_chat(question)
            return streaming_response.response_gen


# Singleton manager instance
rag_engine = RAGEngineManager()

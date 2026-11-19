import os
from dotenv import load_dotenv

from llama_index.core import Settings
from llama_index.llms.groq import Groq
from llama_index.embeddings.jinaai import JinaEmbedding
import qdrant_client
from qdrant_client.http import models

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("UPSTASH_REDIS_URL")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
JINA_API_KEY = os.getenv("JINA_API_KEY")

QDRANT_COLLECTION = "llamareader_knowledge_v3"
EMBEDDING_MODEL_NAME = "jina-embeddings-v3"
EMBEDDING_DIM = 1024


def get_qdrant_client():
    """Return an authenticated Qdrant client instance."""
    if not QDRANT_URL or not QDRANT_API_KEY:
        raise ValueError("QDRANT_URL or QDRANT_API_KEY is missing from .env!")
    return qdrant_client.QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, prefer_grpc=False)


def ensure_qdrant_collection():
    """Ensure the Qdrant Cloud knowledge collection and payload indexes exist."""
    client = get_qdrant_client()
    if not client.collection_exists(QDRANT_COLLECTION):
        print(f"Creating Qdrant Cloud collection '{QDRANT_COLLECTION}'...", flush=True)
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE)
        )
        client.create_payload_index(
            collection_name=QDRANT_COLLECTION,
            field_name="conversation_id",
            field_schema=models.PayloadSchemaType.KEYWORD
        )
        print(f"Qdrant collection '{QDRANT_COLLECTION}' created successfully!", flush=True)


def init_settings():
    """Initialize LlamaIndex LLM, Jina Cloud Embedding, and Qdrant / Upstash engines."""
    if not GROQ_API_KEY:
        print("Warning: GROQ_API_KEY is not set in your .env file!", flush=True)
        
    print("Loading LLM (Groq: openai/gpt-oss-120b)...", flush=True)
    Settings.llm = Groq(
        model="openai/gpt-oss-120b",
        api_key=GROQ_API_KEY
    )
    
    if not JINA_API_KEY:
        print("Warning: JINA_API_KEY is not set in your .env or Render environment!", flush=True)

    print(f"Loading Jina AI Cloud Embedding API ({EMBEDDING_MODEL_NAME})...", flush=True)
    Settings.embed_model = JinaEmbedding(
        api_key=JINA_API_KEY,
        model=EMBEDDING_MODEL_NAME,
        dimensions=EMBEDDING_DIM
    )

    # Initialize Qdrant collection on startup
    if QDRANT_URL and QDRANT_API_KEY:
        try:
            ensure_qdrant_collection()
            print("Connected to Qdrant Cloud Vector Database!", flush=True)
        except Exception as e:
            print(f"Warning: Could not connect to Qdrant Cloud: {e}", flush=True)

    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        print("Upstash Redis credentials configured for Short-Term Memory!", flush=True)

    print("AI Engine ready in memory!", flush=True)

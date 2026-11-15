import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Path to local database file in project root
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "llamareader.db"

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Cloud providers and Neon often provide postgres://, which SQLAlchemy requires as postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    if "neon.tech" in DATABASE_URL and "sslmode" not in DATABASE_URL:
        sep = "&" if "?" in DATABASE_URL else "?"
        DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"
    print("Connecting to Neon PostgreSQL Database...", flush=True)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # Fallback to local SQLite when DATABASE_URL is not set
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    print("Using local SQLite Database (llamareader.db)...", flush=True)
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI dependency to yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Create all database tables if they do not exist."""
    import app.models  # Ensure models are registered
    Base.metadata.create_all(bind=engine)

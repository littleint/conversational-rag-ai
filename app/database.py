import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Normalize postgres:// or postgresql:// to postgresql+psycopg2:// for SQLAlchemy
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

    engine = create_engine(DATABASE_URL)
else:
    DB_PATH = BASE_DIR / "llamareader.db"
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    # check_same_thread=False is needed for SQLite with FastAPI multi-threaded requests
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

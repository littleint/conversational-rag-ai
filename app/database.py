from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Path to database file in project root
BASE_DIR = Path(__file__).resolve().parent.parent
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

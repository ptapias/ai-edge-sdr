"""
Database configuration with SQLAlchemy for PostgreSQL (Supabase).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import get_settings

settings = get_settings()

# Get database URL from settings
SQLALCHEMY_DATABASE_URL = settings.database_url

# Create SQLAlchemy engine
# Note: No connect_args needed for PostgreSQL (that was SQLite-specific)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base for models
Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database by creating all tables."""
    from . import models  # Import to register models
    Base.metadata.create_all(bind=engine)

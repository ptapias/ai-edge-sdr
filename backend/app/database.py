"""
Database configuration with SQLAlchemy for PostgreSQL (Supabase).
"""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import get_settings

logger = logging.getLogger(__name__)

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


def run_migrations():
    """Run manual migrations for columns that create_all() won't add to existing tables."""
    migrations = [
        # Smart Pipeline columns on sequences table
        "ALTER TABLE sequences ADD COLUMN IF NOT EXISTS sequence_mode VARCHAR(20) DEFAULT 'classic'",
        # Smart Pipeline columns on sequence_enrollments table
        "ALTER TABLE sequence_enrollments ADD COLUMN IF NOT EXISTS current_phase VARCHAR(20)",
        "ALTER TABLE sequence_enrollments ADD COLUMN IF NOT EXISTS phase_entered_at TIMESTAMP",
        "ALTER TABLE sequence_enrollments ADD COLUMN IF NOT EXISTS last_response_at TIMESTAMP",
        "ALTER TABLE sequence_enrollments ADD COLUMN IF NOT EXISTS last_response_text TEXT",
        "ALTER TABLE sequence_enrollments ADD COLUMN IF NOT EXISTS phase_analysis TEXT",
        "ALTER TABLE sequence_enrollments ADD COLUMN IF NOT EXISTS messages_in_phase INTEGER DEFAULT 0",
        "ALTER TABLE sequence_enrollments ADD COLUMN IF NOT EXISTS nurture_count INTEGER DEFAULT 0",
        "ALTER TABLE sequence_enrollments ADD COLUMN IF NOT EXISTS reactivation_count INTEGER DEFAULT 0",
        "ALTER TABLE sequence_enrollments ADD COLUMN IF NOT EXISTS total_messages_sent INTEGER DEFAULT 0",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception as e:
                logger.warning(f"Migration skipped: {e}")
        conn.commit()
    logger.info("Database migrations completed")


def init_db():
    """Initialize database by creating all tables, then run column migrations."""
    from . import models  # Import to register models
    Base.metadata.create_all(bind=engine)
    try:
        run_migrations()
    except Exception as e:
        logger.warning(f"Migration step failed (tables may not exist yet): {e}")

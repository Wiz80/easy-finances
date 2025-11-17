"""
Database configuration and session management.
Uses SQLAlchemy 2.x with both sync and async support.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# SQLAlchemy Base for ORM models
Base = declarative_base()

# Sync engine and session
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.environment == "development",
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Async engine and session (for future async endpoints)
# Note: Lazy initialization to avoid requiring asyncpg during migrations
_async_engine = None
_async_session_local = None


def get_async_engine():
    """Get or create async engine lazily."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.async_database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            echo=settings.environment == "development",
        )
    return _async_engine


def get_async_session_local():
    """Get or create async session factory lazily."""
    global _async_session_local
    if _async_session_local is None:
        _async_session_local = sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _async_session_local


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI endpoints to get a database session.
    
    Yields:
        SQLAlchemy Session
        
    Example:
        @app.get("/expenses")
        def get_expenses(db: Session = Depends(get_db)):
            return db.query(Expense).all()
    """
    db = SessionLocal()
    try:
        logger.debug("database_session_created")
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("database_session_error", error=str(e), exc_info=True)
        raise
    finally:
        db.close()
        logger.debug("database_session_closed")


async def get_async_db() -> AsyncSession:
    """
    Async dependency for FastAPI endpoints to get an async database session.
    
    Yields:
        Async SQLAlchemy Session
    """
    session_factory = get_async_session_local()
    async with session_factory() as session:
        try:
            logger.debug("async_database_session_created")
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error("async_database_session_error", error=str(e), exc_info=True)
            raise
        finally:
            await session.close()
            logger.debug("async_database_session_closed")


def init_db() -> None:
    """
    Initialize database tables.
    Only used for development/testing. Production uses Alembic migrations.
    """
    logger.info("initializing_database_tables")
    Base.metadata.create_all(bind=engine)
    logger.info("database_tables_created")


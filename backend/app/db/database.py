"""
Database connection and session management.
Uses SQLAlchemy 2.0 async with asyncpg driver.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create async engine - will be None if no database URL configured
engine = None
AsyncSessionLocal = None

if settings.database_url:
    # Convert PostgresDsn to string and ensure async driver
    db_url = str(settings.database_url)
    if "postgresql://" in db_url and "postgresql+asyncpg://" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        db_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=settings.debug,
        pool_pre_ping=True,
    )

    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session with automatic commit/rollback.

    Raises:
        RuntimeError: If database is not configured.
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not configured. Set DATABASE_URL environment variable.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Initialize database connection pool.
    Called during application startup.
    """
    if engine is None:
        logger.warning("database_not_configured", message="DATABASE_URL not set")
        return

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("database_connected", pool_size=settings.db_pool_size)
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        raise


async def close_db() -> None:
    """
    Close database connection pool.
    Called during application shutdown.
    """
    if engine is not None:
        await engine.dispose()
        logger.info("database_disconnected")

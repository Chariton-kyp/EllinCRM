"""Read-only database session provider for the chat agent.

The chat agent's structured tools (count, aggregate, group_by, search, get_record)
must ONLY read from the database. This module provides a dedicated async session
maker backed by a read-only Postgres role (`ellincrm_readonly`) with a short
`statement_timeout`.

Defense in depth: even if a bug in a tool allowed SQL injection, the Postgres
role itself refuses any INSERT/UPDATE/DELETE/DDL operations and caps query time
at 3 seconds to prevent cartesian joins or accidental full-table scans from
stalling the chat.

If the readonly role is not configured (e.g. local dev without Alembic migration
applied yet), this module gracefully falls back to the normal session with a
warning. Tools should still behave correctly — the protection is belt-and-suspenders.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level readonly session maker (lazily initialized on first use)
_readonly_engine = None
_ReadonlySessionLocal: async_sessionmaker[AsyncSession] | None = None


def _build_readonly_url() -> str | None:
    """Build the readonly connection URL.

    Prefers a dedicated `READONLY_DATABASE_URL` if set, otherwise rewrites the
    main `DATABASE_URL` to connect as `ellincrm_readonly`. Returns None if the
    main database is not configured at all (nothing to read from).
    """
    # Prefer explicit readonly URL if the operator provided one
    explicit = getattr(settings, "readonly_database_url", None)
    if explicit:
        url = str(explicit)
        if "postgresql://" in url and "postgresql+asyncpg://" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://")
        return url

    if not settings.database_url:
        return None

    # Rewrite the main URL to use the readonly role.
    # Format: postgresql+asyncpg://user:pass@host:port/db
    # We replace the user portion with `ellincrm_readonly` and the password
    # portion with the value of `READONLY_DB_PASSWORD` (from env).
    main_url = str(settings.database_url)
    if "postgresql://" in main_url and "postgresql+asyncpg://" not in main_url:
        main_url = main_url.replace("postgresql://", "postgresql+asyncpg://")

    readonly_password = settings.readonly_db_password_value
    if not readonly_password:
        # Same password as main user — only acceptable in dev
        logger.warning(
            "readonly_password_not_set",
            message="READONLY_DB_PASSWORD not set; reusing main DB password. "
            "This is acceptable in dev but should be a separate secret in prod.",
        )
        return main_url

    # Parse and rewrite credentials
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(main_url)
        netloc_parts = parsed.netloc.split("@", 1)
        host_port = netloc_parts[-1]
        new_netloc = f"ellincrm_readonly:{readonly_password}@{host_port}"
        return urlunparse(parsed._replace(netloc=new_netloc))
    except Exception as exc:
        logger.warning("readonly_url_parse_failed", error=str(exc))
        return main_url


def _init_readonly_engine() -> None:
    """Initialize the module-level readonly engine and session maker."""
    global _readonly_engine, _ReadonlySessionLocal

    if _ReadonlySessionLocal is not None:
        return  # Already initialized

    url = _build_readonly_url()
    if url is None:
        logger.warning(
            "readonly_session_not_configured",
            message="No database URL available; readonly session falls back to main.",
        )
        return

    # Smaller pool — chat traffic is bursty, doesn't warrant a full pool
    _readonly_engine = create_async_engine(
        url,
        pool_size=3,
        max_overflow=5,
        pool_pre_ping=True,
        echo=False,
    )

    _ReadonlySessionLocal = async_sessionmaker(
        _readonly_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    logger.info("readonly_session_initialized", pool_size=3)


@asynccontextmanager
async def get_readonly_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager yielding a read-only SQLAlchemy session.

    Usage:
        async with get_readonly_session() as session:
            result = await session.execute(text("SELECT ..."))

    - Sets `statement_timeout = 3s` at session level as an extra safety net
      (the role also sets it, but this handles dev environments where the
      readonly role is not yet created).
    - Never commits; sessions are read-only by intent.
    - Rolls back any accidentally uncommitted state on exit.

    Falls back to the main session maker if the readonly role is not
    configured, with a logged warning. Tools should still function correctly.
    """
    global _ReadonlySessionLocal

    if _ReadonlySessionLocal is None:
        _init_readonly_engine()

    # Fallback to main session if readonly not configured
    if _ReadonlySessionLocal is None:
        from app.db.database import AsyncSessionLocal

        if AsyncSessionLocal is None:
            raise RuntimeError("No database session available. Configure DATABASE_URL.")
        session_maker = AsyncSessionLocal
    else:
        session_maker = _ReadonlySessionLocal

    async with session_maker() as session:
        try:
            # Belt-and-suspenders statement timeout. Using SET (session-level)
            # instead of SET LOCAL because SET LOCAL only persists within a
            # transaction — if SQLAlchemy autocommits or a tool rolls back
            # mid-flight, SET LOCAL would be lost. Session-level SET persists
            # until the connection is returned to the pool (which is fine
            # since we always rollback in the finally block).
            await session.execute(text("SET statement_timeout = '3s'"))
            yield session
        finally:
            # Readonly by intent: no commit, always rollback any accidental writes
            await session.rollback()


async def close_readonly_engine() -> None:
    """Dispose of the readonly engine on app shutdown."""
    global _readonly_engine, _ReadonlySessionLocal
    if _readonly_engine is not None:
        await _readonly_engine.dispose()
        _readonly_engine = None
        _ReadonlySessionLocal = None
        logger.info("readonly_session_closed")

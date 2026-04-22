"""
PSEUDOCODE:
1. Async engine, sessionmaker, and FastAPI dependency for AsyncSession.
2. Plus a synchronous `get_sync_session()` helper for scripts/seed_*.py (G5).
3. G11: async URL uses `sqlite+aiosqlite://`; sync URL uses `sqlite:///`.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_async_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def _async_url() -> str:
    """Return DATABASE_URL, coercing plain sqlite:// to sqlite+aiosqlite://."""
    url = get_settings().DATABASE_URL
    if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def _sync_url() -> str:
    """Return the sync equivalent of DATABASE_URL (drops aiosqlite driver)."""
    url = get_settings().DATABASE_URL
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite:///", 1).replace("sqlite:////", "sqlite:///", 1)
    return url


def get_engine() -> AsyncEngine:
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(_async_url(), echo=get_settings().DEBUG, future=True)
    return _async_engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency. Yields a session; commits on clean exit, rolls back on error."""
    maker = get_sessionmaker()
    async with maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _async_engine, _AsyncSessionLocal
    if _async_engine is not None:
        await _async_engine.dispose()
    _async_engine = None
    _AsyncSessionLocal = None


# ---------------------------------------------------------------------------
# Synchronous session factory for scripts (seed_db.py, seed_traces.py).  [G5]
# ---------------------------------------------------------------------------

_sync_engine = None
_SyncSessionLocal: sessionmaker[Session] | None = None


def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(_sync_url(), echo=False, future=True)
    return _sync_engine


def get_sync_session() -> Generator[Session, None, None]:
    """Sync context manager for scripts. Usage:
        with next(get_sync_session()) as session: ...
    Or imperatively:
        gen = get_sync_session(); s = next(gen); ... ; gen.close()
    """
    global _SyncSessionLocal
    if _SyncSessionLocal is None:
        _SyncSessionLocal = sessionmaker(bind=get_sync_engine(), class_=Session, expire_on_commit=False)
    with _SyncSessionLocal() as session:
        yield session


# Phase 2 Graduation: swap SQLite+aiosqlite for Postgres+asyncpg via DATABASE_URL env swap only;
# add pool_size / max_overflow / pre-ping config; add a read-replica factory when concurrency >4.

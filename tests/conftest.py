"""
Shared test fixtures for ds-meal.
- `db_url` — a per-test SQLite file in tmp_path, using the aiosqlite async driver.
- `seeded_db` — sets DATABASE_URL env var and runs scripts.seed_db.main() once so Recipe tables are populated.
- `client` — httpx.AsyncClient bound to the FastAPI app with the per-test DB.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def db_url(tmp_path) -> str:
    """One fresh SQLite file per test, aiosqlite driver."""
    db_file = tmp_path / "test.db"
    return f"sqlite+aiosqlite:///{db_file}"


@pytest_asyncio.fixture
async def seeded_db(db_url, monkeypatch) -> str:
    """Seed the fixtures/recipes.json catalog into the test DB. Returns DATABASE_URL."""
    monkeypatch.setenv("DATABASE_URL", db_url)

    # Reset the app.config singleton so the new env var is picked up.
    from app.config import get_settings
    get_settings.cache_clear()

    # Reset db module singletons so they rebind to the test URL.
    from app.db import database as db_mod
    db_mod._async_engine = None
    db_mod._AsyncSessionLocal = None
    db_mod._sync_engine = None
    db_mod._SyncSessionLocal = None

    # Run the seeder (sync engine, uses _sync_url derived from DATABASE_URL).
    from scripts import seed_db
    seed_db.main()

    return db_url


@pytest_asyncio.fixture
async def client(seeded_db) -> AsyncIterator:
    """httpx.AsyncClient bound to the real FastAPI app, with the seeded test DB."""
    # Import late so env var and db singletons are already reset.
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()
    # Manually run lifespan to trigger init_schema (tables are created by seed_db, but
    # init_schema is a no-op on existing tables — safe to run twice).
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

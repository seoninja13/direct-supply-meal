"""
PSEUDOCODE:
1. FastAPI application factory. Wires routes, static files, Jinja templates, startup init_schema.
2. `app = create_app()` at module level so `uvicorn app.main:app` works.
3. Slice A surface: public (/, /health, /sign-in placeholders) and recipes routers.
   Subsequent slices add facility, meal_plans, orders, calendar, agents.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.db.init_schema import init_schema  # G12 — correct import path

APP_ROOT = Path(__file__).parent
TEMPLATE_DIR = APP_ROOT / "templates"
STATIC_DIR = APP_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_schema()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="ds-meal",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    application.state.templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

    # Register routers — Slice A: public + recipes. Slice B: facility.
    from app.routes import facility, public, recipes

    application.include_router(public.router)
    application.include_router(public.api_router)
    application.include_router(recipes.router)
    application.include_router(recipes.api_router)
    application.include_router(facility.router)
    application.include_router(facility.api_router)

    return application


app = create_app()


# Phase 2 Graduation: swap init_schema() for Alembic migration entry point; register Inngest
# client on startup; add other routers (facility, meal_plans, orders, calendar, agents) in Slices B-E.

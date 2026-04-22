"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - FastAPI application factory for ds-meal; wires routes, static files, Jinja templates,
     startup DB schema init, and the /health endpoint per DOMAIN-WORKFLOW §10.
2. Ordered steps.
   a. Define create_app() -> FastAPI: the single entry point uvicorn / tests call.
   b. Inside create_app():
        - instantiate FastAPI(title="ds-meal", debug=settings.DEBUG).
        - mount StaticFiles at /static pointing at app/static.
        - register Jinja2Templates pointing at app/templates, attach to app.state.templates.
        - include_router for each module under app/routes/ (public, recipes, facility,
          meal_plans, orders, calendar, agents).
        - register startup event that calls app/db/session.init_schema() to create tables.
        - register /health (returns {"status":"ok"}) and its JSON twin /api/v1/health
          in app/routes/public.py; nothing else lives at module level here.
   c. Module-level `app = create_app()` so uvicorn's default app:app target works.
3. Inputs / Outputs.
   - Inputs: app/config.Settings (env-loaded), routers, templates dir, static dir.
   - Outputs: a ready-to-serve FastAPI ASGI app.
4. Side effects.
   - At startup: creates SQLite tables if missing (idempotent).
   - Registers request routing and static-file mounts.

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


def create_app() -> FastAPI:
    # PSEUDO: Build and wire the FastAPI application.
    #   1. Load Settings via get_settings() (memoized).
    #   2. app = FastAPI(title="ds-meal", debug=settings.DEBUG, version="0.1.0").
    #   3. app.mount("/static", StaticFiles(directory="app/static"), name="static").
    #   4. templates = Jinja2Templates(directory="app/templates"); app.state.templates = templates.
    #   5. Import routers lazily to keep import-time side effects minimal:
    #        from app.routes import public, recipes, facility, meal_plans, orders, calendar, agents
    #      app.include_router(public.router)
    #      app.include_router(recipes.router)
    #      app.include_router(facility.router)
    #      app.include_router(meal_plans.router)
    #      app.include_router(orders.router)
    #      app.include_router(calendar.router)
    #      app.include_router(agents.router)
    #   6. Register startup handler that invokes app.db.session.init_schema() to create all
    #      SQLModel tables against DATABASE_URL (safe to re-run; CREATE TABLE IF NOT EXISTS).
    #   7. Return app.
    raise NotImplementedError


# PSEUDO: module-level ASGI target so `uvicorn app.main:app` works without a factory flag.
#   In Phase 4 this becomes `app = create_app()`. During Phase 3 the attribute is declared so
#   tooling (import linters, static analysers) can resolve `app.main:app` without executing.
app: "FastAPI | None" = None


# Phase 2 Graduation: swap `init_schema()` for an Alembic migration entry point and register an
# Inngest client on startup so durable agent dispatch can flow through the same ASGI app.

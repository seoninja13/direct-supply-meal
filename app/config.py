"""
PSEUDOCODE:
1. One-line summary of module purpose.
   - Centralized application settings loaded from environment / .env via pydantic-settings.
2. Ordered steps.
   a. Declare a Settings class deriving from BaseSettings.
   b. Declare required fields (Anthropic, Clerk, DB) and optional flags (DEBUG, LOG_LEVEL).
   c. Configure pydantic to read from a .env file and environment variables (case-insensitive).
   d. Expose a cached accessor get_settings() so the object is instantiated once per process.
3. Inputs / Outputs.
   - Inputs: process env + optional .env file at repo root.
   - Outputs: a validated Settings instance consumed by FastAPI dependencies, DB factory, auth.
4. Side effects.
   - None at import time beyond reading env. get_settings() is memoized via functools.lru_cache
     to avoid repeated env parsing across requests.

IMPLEMENTATION: Phase 4 — see functions below.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PSEUDO: Settings fields sourced from environment.
    #   - ANTHROPIC_API_KEY: Claude Agent SDK credential (required for agent drivers).
    #   - CLERK_PUBLISHABLE_KEY: frontend-facing Clerk key (non-secret).
    #   - CLERK_SECRET_KEY: backend Clerk key for webhook + Backend API use.
    #   - CLERK_JWKS_URL: JWKS endpoint used to verify session JWTs.
    #   - DATABASE_URL: SQLAlchemy URL (sqlite:/// for Phase 1, Postgres seam for Phase 2).
    #   - DEBUG: bool toggling verbose logging / autoreload.
    #   - LOG_LEVEL: string like INFO / DEBUG / WARNING consumed by logging config.
    # PSEUDO: model_config points pydantic-settings at .env and enforces case-insensitive loading.
    ANTHROPIC_API_KEY: str
    CLERK_PUBLISHABLE_KEY: str
    CLERK_SECRET_KEY: str
    CLERK_JWKS_URL: str
    DATABASE_URL: str
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # PSEUDO: Return the singleton Settings instance.
    #   1. Construct Settings() — pydantic reads env + .env.
    #   2. Cached via lru_cache so subsequent calls are O(1).
    #   3. Raises ValidationError at first call if required vars are missing.
    raise NotImplementedError


# Phase 2 Graduation: add provider-specific settings blocks (Postgres pool size, Inngest signing key,
# supplier ERP creds) and split secrets into a vault-backed SecretSettings sub-class.

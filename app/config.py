"""
PSEUDOCODE:
1. Centralized application settings loaded from environment / .env via pydantic-settings.
2. No metered ANTHROPIC_API_KEY — Claude Agent SDK uses the Claude Max subscription via
   OAuth credentials mounted on the host.
3. lru_cache makes get_settings() idempotent across requests.

IMPLEMENTATION: Phase 4.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Clerk — "DS-Meal" Development app. Google provider only.
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = ""
    CLERK_SIGN_IN_URL: str = ""  # G6 — referenced by routes/public.py::sign_in_redirect

    # Database — SQLite via aiosqlite driver in the app; sync driver used by scripts.
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/ds-meal.db"  # G11

    # Runtime
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env.ds-meal",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Phase 2 Graduation: split into SecretSettings backed by Vault/Doppler; add Inngest signing key,
# Postgres pool size, supplier ERP credentials.

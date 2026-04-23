"""Unit tests for app.auth.app_session — mint/verify roundtrip + error paths.

Covers commit 219e91b: 1h app-session tokens signed with CLERK_SECRET_KEY.
"""

from __future__ import annotations

import time

import jwt
import pytest

from app.auth.app_session import (
    APP_SESSION_TTL_SECONDS,
    AppSession,
    mint_app_session,
    verify_app_session,
)
from app.auth.clerk_middleware import AuthError
from app.config import get_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Ensure each test re-reads env via Settings."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_mint_and_verify_roundtrip(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_roundtrip_secret")
    get_settings.cache_clear()

    token = mint_app_session(sub="user_clerk_abc", email="admin@dulocore.com")
    assert isinstance(token, str) and token.count(".") == 2

    session = verify_app_session(token)
    assert isinstance(session, AppSession)
    assert session.sub == "user_clerk_abc"
    assert session.email == "admin@dulocore.com"
    assert session.expires_at - session.issued_at == APP_SESSION_TTL_SECONDS


def test_verify_expired_token_raises(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_expired")
    get_settings.cache_clear()

    now = int(time.time())
    expired_token = jwt.encode(
        {
            "iss": "ds-meal",
            "sub": "user_x",
            "email": "x@dulocore.com",
            "iat": now - 7200,
            "exp": now - 60,
        },
        "sk_test_expired",
        algorithm="HS256",
    )

    with pytest.raises(AuthError) as excinfo:
        verify_app_session(expired_token)
    assert "app_session_invalid" in str(excinfo.value)


def test_verify_wrong_signature_raises(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_minted_with")
    get_settings.cache_clear()

    token = mint_app_session(sub="user_y", email="y@dulocore.com")

    # Now swap the secret; verify should fail because signature won't match.
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_different_secret")
    get_settings.cache_clear()

    with pytest.raises(AuthError) as excinfo:
        verify_app_session(token)
    assert "app_session_invalid" in str(excinfo.value)


def test_verify_missing_email_claim_raises(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_no_email")
    get_settings.cache_clear()

    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "ds-meal",
            "sub": "user_no_email",
            "iat": now,
            "exp": now + 3600,
        },
        "sk_test_no_email",
        algorithm="HS256",
    )

    with pytest.raises(AuthError) as excinfo:
        verify_app_session(token)
    assert "app_session_invalid" in str(excinfo.value)


def test_verify_missing_sub_claim_raises(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_no_sub")
    get_settings.cache_clear()

    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "ds-meal",
            "email": "nosub@dulocore.com",
            "iat": now,
            "exp": now + 3600,
        },
        "sk_test_no_sub",
        algorithm="HS256",
    )

    with pytest.raises(AuthError) as excinfo:
        verify_app_session(token)
    assert "app_session_invalid" in str(excinfo.value)


def test_verify_wrong_issuer_raises(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_bad_iss")
    get_settings.cache_clear()

    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "some-other-issuer",
            "sub": "user_iss",
            "email": "iss@dulocore.com",
            "iat": now,
            "exp": now + 3600,
        },
        "sk_test_bad_iss",
        algorithm="HS256",
    )

    with pytest.raises(AuthError) as excinfo:
        verify_app_session(token)
    assert "app_session_invalid" in str(excinfo.value)


def test_verify_empty_token_raises_missing_token(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_empty")
    get_settings.cache_clear()

    with pytest.raises(AuthError) as excinfo:
        verify_app_session("")
    assert "missing_token" in str(excinfo.value)


def test_verify_non_string_raises_missing_token(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_nonstr")
    get_settings.cache_clear()

    with pytest.raises(AuthError) as excinfo:
        verify_app_session(None)  # type: ignore[arg-type]
    assert "missing_token" in str(excinfo.value)

    with pytest.raises(AuthError) as excinfo:
        verify_app_session(12345)  # type: ignore[arg-type]
    assert "missing_token" in str(excinfo.value)


def test_mint_without_secret_raises(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(AuthError) as excinfo:
        mint_app_session(sub="user_z", email="z@dulocore.com")
    assert "APP_SESSION_SECRET missing" in str(excinfo.value)


def test_app_session_ttl_is_one_hour(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_ttl")
    get_settings.cache_clear()

    token = mint_app_session(sub="user_ttl", email="ttl@dulocore.com")
    # Decode without verification to inspect the payload directly.
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["exp"] - payload["iat"] == 3600
    assert APP_SESSION_TTL_SECONDS == 3600

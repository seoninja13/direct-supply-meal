"""Integration tests for _fetch_clerk_user_email — Clerk Backend API fallback.

Covers commit dcf8749: fall back to Clerk Backend API when session JWT lacks
an email claim.
"""

from __future__ import annotations

import httpx
import pytest

from app.auth import clerk_middleware
from app.auth.clerk_middleware import _fetch_clerk_user_email
from app.config import get_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeResponse:
    """Minimal stand-in for httpx.Response that supports .raise_for_status() and .json()."""

    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=None, response=None  # type: ignore[arg-type]
            )

    def json(self) -> dict:
        return self._payload


def test_primary_email_returned(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_primary")
    get_settings.cache_clear()

    payload = {
        "primary_email_address_id": "email_1",
        "email_addresses": [
            {"id": "email_0", "email_address": "secondary@x.com"},
            {"id": "email_1", "email_address": "primary@x.com"},
        ],
    }

    def fake_get(url, headers=None, timeout=None):
        assert url == "https://api.clerk.com/v1/users/user_abc"
        assert headers == {"Authorization": "Bearer sk_test_primary"}
        assert timeout == 5.0
        return _FakeResponse(payload)

    monkeypatch.setattr(clerk_middleware.httpx, "get", fake_get)

    result = _fetch_clerk_user_email("user_abc")
    assert result == "primary@x.com"


def test_falls_back_to_first_email_when_no_primary(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_fallback")
    get_settings.cache_clear()

    payload = {
        "primary_email_address_id": None,
        "email_addresses": [
            {"id": "email_0", "email_address": "first@x.com"},
            {"id": "email_1", "email_address": "second@x.com"},
        ],
    }

    def fake_get(url, headers=None, timeout=None):
        return _FakeResponse(payload)

    monkeypatch.setattr(clerk_middleware.httpx, "get", fake_get)

    result = _fetch_clerk_user_email("user_def")
    assert result == "first@x.com"


def test_returns_none_on_http_error(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_http_err")
    get_settings.cache_clear()

    def fake_get(url, headers=None, timeout=None):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(clerk_middleware.httpx, "get", fake_get)

    assert _fetch_clerk_user_email("user_err") is None


def test_returns_none_when_secret_empty(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "")
    get_settings.cache_clear()

    def fake_get(url, headers=None, timeout=None):
        raise AssertionError("httpx.get should not be called when secret is empty")

    monkeypatch.setattr(clerk_middleware.httpx, "get", fake_get)

    assert _fetch_clerk_user_email("user_whatever") is None


def test_returns_none_when_user_id_empty(monkeypatch):
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_no_user")
    get_settings.cache_clear()

    def fake_get(url, headers=None, timeout=None):
        raise AssertionError("httpx.get should not be called when user_id is empty")

    monkeypatch.setattr(clerk_middleware.httpx, "get", fake_get)

    assert _fetch_clerk_user_email("") is None

"""
Test helpers for Clerk JWT auth.

Spins up a tiny HTTP server on 127.0.0.1 that serves a JWKS document, mints
RS256-signed session JWTs with the matching private key, and lets the app's
`verify_clerk_jwt()` path run unmodified against the local key.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_KEY_ID = "test-key-1"

# Generate a single ephemeral keypair per test-process run.
_PRIVATE_KEY: rsa.RSAPrivateKey = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

_PRIVATE_PEM = _PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _jwks_document() -> dict:
    numbers = _PUBLIC_KEY.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "kid": _KEY_ID,
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") in ("", "/.well-known/jwks.json", "/jwks.json"):
            body = json.dumps(_jwks_document()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_args, **_kwargs):  # quiet the test output
        pass


class JWKSServer:
    """A tiny threaded HTTP server that serves our test JWKS at /jwks.json."""

    def __init__(self) -> None:
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port: int = 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}/jwks.json"

    def start(self) -> None:
        self._httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self._port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        self._thread = None


def mint_session_token(
    *,
    sub: str,
    email: str,
    iat: int | None = None,
    exp: int | None = None,
) -> str:
    """Mint an RS256 JWT that the app's verify_clerk_jwt will accept."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "iat": iat if iat is not None else now - 10,
        "exp": exp if exp is not None else now + 3600,
        "sid": "sess_test_" + sub,
        "iss": "https://test.clerk.accounts.dev",
    }
    return jwt.encode(
        payload,
        _PRIVATE_PEM,
        algorithm="RS256",
        headers={"kid": _KEY_ID},
    )

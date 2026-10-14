"""Password hashing and session-token helpers.

Uses standard, proven primitives only (PBKDF2-HMAC-SHA256 via ``hashlib``, CSPRNG via
``secrets``). No home-grown cryptography. Plaintext passwords and raw session tokens are never
persisted or logged.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

_PBKDF2_ALGORITHM = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 600_000
_SESSION_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    """Return a salted PBKDF2-HMAC-SHA256 hash string (algorithm + iterations + salt + digest)."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ALGORITHM}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification of a password against a stored hash."""
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != _PBKDF2_ALGORITHM:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def generate_session_token() -> str:
    """Generate an opaque, high-entropy session token (returned to the client once)."""
    return secrets.token_urlsafe(_SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Hash a session token for storage (never store the raw token)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

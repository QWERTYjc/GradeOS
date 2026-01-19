"""Password hashing utilities."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Tuple


_ALGO = "pbkdf2_sha256"
_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "120000"))


def _derive_key(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def _encode_parts(salt: bytes, digest: bytes) -> Tuple[str, str]:
    return (
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2."""
    if not password:
        raise ValueError("Password must not be empty")
    salt = os.urandom(16)
    digest = _derive_key(password, salt, _ITERATIONS)
    salt_b64, digest_b64 = _encode_parts(salt, digest)
    return f"{_ALGO}${_ITERATIONS}${salt_b64}${digest_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash string."""
    try:
        algo, iter_str, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if algo != _ALGO:
            return False
        iterations = int(iter_str)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
    except Exception:
        return False

    digest = _derive_key(password, salt, iterations)
    return hmac.compare_digest(digest, expected)

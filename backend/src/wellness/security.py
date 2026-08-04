"""Minimal password hashing for the smoke-test CRUD endpoints.

TODO: these endpoints have no auth at all yet (see api/v1/users.py). Replace
this with a real password-hashing library (e.g. passlib/bcrypt or argon2)
before any login/auth flow is built on top of it.
"""

import hashlib
import secrets

_ALGORITHM = "sha256"
_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        _ALGORITHM, password.encode(), bytes.fromhex(salt), _ITERATIONS
    ).hex()
    return f"pbkdf2_{_ALGORITHM}${_ITERATIONS}${salt}${digest}"

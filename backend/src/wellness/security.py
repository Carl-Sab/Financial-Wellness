"""Password hashing and JWT access tokens.

Password hashing is intentionally simple (PBKDF2-SHA256 via stdlib, no
third-party dependency) — see hash_password/verify_password. Iteration
count is read back out of the stored hash on verify, not hardcoded, so
_ITERATIONS can change for new hashes without invalidating old ones.

Access tokens are short-lived JWTs (see create_access_token/
decode_access_token): stateless, verified by signature alone, never stored
anywhere. That statelessness is also their limit — a JWT can't be revoked,
only left to expire — which is why session-level control (logout, theft
detection) lives in the refresh_tokens table instead. See models/auth.py.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from wellness.config import get_settings

_ALGORITHM = "sha256"
_ITERATIONS = 200_000

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        _ALGORITHM, password.encode(), bytes.fromhex(salt), _ITERATIONS
    ).hex()
    return f"pbkdf2_{_ALGORITHM}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    """True iff `password` hashes to `password_hash`, using that hash's own
    stored algorithm/iteration count/salt — never the caller's assumptions
    about them. Malformed hashes fail closed (return False) rather than
    raising, since a corrupt stored hash should never be indistinguishable
    from a server error.
    """
    try:
        algorithm_label, iterations_str, salt, expected_digest = password_hash.split("$")
        algorithm = algorithm_label.removeprefix("pbkdf2_")
        iterations = int(iterations_str)
        actual_digest = hashlib.pbkdf2_hmac(
            algorithm, password.encode(), bytes.fromhex(salt), iterations
        ).hex()
    except (ValueError, TypeError):
        return False
    # Constant-time: a digest-length timing difference on early mismatch
    # would leak information a simple `==` comparison wouldn't.
    return secrets.compare_digest(actual_digest, expected_digest)


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    """The user_id a valid, unexpired access token was issued for, or None
    for anything else (expired, bad signature, malformed, wrong subject
    format) — callers don't need to know PyJWT's exception hierarchy to
    turn a bad token into a 401.

    algorithms=[JWT_ALGORITHM] is passed explicitly and is not optional:
    PyJWT only trusts algorithms named here, never the token's own `alg`
    header. Accepting whatever the header claims is how algorithm-confusion
    attacks work — e.g. a token signed with `alg: none`, or (worse, for
    RS256-capable setups) one signed with the server's own public key
    treated as an HMAC secret. Pinning the algorithm server-side closes
    that off regardless of what the token claims about itself.
    """
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError, TypeError):
        return None

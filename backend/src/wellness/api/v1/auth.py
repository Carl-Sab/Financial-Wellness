"""Registration, login, and JWT session management.

Token strategy: access tokens are short-lived JWTs (15 min, see security.py),
returned in the response body only — the frontend is expected to hold them
in memory, never localStorage/sessionStorage, since anything readable by JS
is readable by an XSS payload too. Refresh tokens are the opposite: opaque
30-day random strings, delivered as an httpOnly cookie (so JS can't read
them even if it wanted to) and stored server-side as a hash in
refresh_tokens — see models/auth.py for why that's what makes revocation
possible at all.

Distinct from POST /api/v1/users (users.py): that stays the unauthenticated,
unvalidated smoke-test CRUD endpoint it always was.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import get_current_user
from wellness.config import get_settings
from wellness.db import get_session
from wellness.models import (
    BankAccount,
    LoginFailure,
    RefreshToken,
    User,
    UserNormalizationSnapshot,
)
from wellness.models.normalization_snapshots import POPULATION_NORMALIZATION_DEFAULTS
from wellness.schemas.auth import AccessTokenResponse, LoginRequest, RegisterRequest
from wellness.schemas.users import UserRead
from wellness.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8

REFRESH_TOKEN_EXPIRE_DAYS = 30
REFRESH_COOKIE_NAME = "refresh_token"
# Scoped to this router, not the whole API: no other endpoint needs the
# refresh token, so there's no reason to hand it to them on every request.
REFRESH_COOKIE_PATH = "/api/v1/auth"

LOGIN_RATE_LIMIT_MAX_FAILURES = 5
LOGIN_RATE_LIMIT_WINDOW_MINUTES = 15
GENERIC_LOGIN_ERROR = "Incorrect email or password"

# Hashed once at import time, not per-request: verify_password is run
# against this whenever the submitted email doesn't match a real (active)
# user, so a login attempt costs the same PBKDF2 work either way. Without
# this, "no such account" would return measurably faster than "wrong
# password" — a timing side channel that leaks exactly what the generic
# GENERIC_LOGIN_ERROR message is meant to hide.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_hex(32))


@router.post("/register", response_model=UserRead, status_code=201)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_session)) -> User:
    # Checked here rather than as a Field(min_length=...) constraint:
    # FastAPI's default validation-error response echoes back the
    # offending input value, and a password must never appear in a log or
    # a response body — see security.py's module note. A plain
    # HTTPException gives full control over what the error body contains.
    if len(payload.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
        )

    data = payload.model_dump(exclude={"password"})
    user = User(**data, password_hash=hash_password(payload.password))

    try:
        session.add(user)
        # Flushed, not committed: user.id is server-generated (gen_random_uuid())
        # and the dependent rows below need it, but every insert must still land
        # in a single transaction — one commit for all, and
        # the rollback on failure undoes all of them together.
        await session.flush()
        # A bank account exists from day one so nothing downstream (goals,
        # transactions, the eventual budget onboarding step) has to handle
        # a user with no account yet. No ledger entries — an empty account
        # is a real, valid state; balance is always derived, never stored.
        session.add(
            BankAccount(
                user_id=user.id,
                account_number=f"ACC-{user.id.hex[:12].upper()}",
                currency=user.currency,
            )
        )
        session.add(
            UserNormalizationSnapshot(
                user_id=user.id,
                **POPULATION_NORMALIZATION_DEFAULTS,
            )
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc.orig)) from exc

    await session.refresh(user)
    return user


def _hash_refresh_token(raw_token: str) -> str:
    # Plain SHA-256, not a slow/salted hash like password_hash: the raw
    # token is already 32 bytes of CSPRNG output, not a human-chosen
    # secret, so brute-forcing it is infeasible regardless of hash speed.
    # What matters here is a fast, deterministic, indexable lookup on every
    # refresh request — see models/auth.py.
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        # Secure requires HTTPS, which plain-HTTP localhost dev doesn't
        # have. environment=="local" is the same signal logging.py already
        # uses to distinguish dev from anything real — see config.py.
        secure=settings.environment != "local",
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


async def _issue_refresh_token(
    session: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID
) -> str:
    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_hash_refresh_token(raw_token),
            family_id=family_id,
            issued_at=now,
            expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return raw_token


async def _revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    payload: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)
) -> AccessTokenResponse:
    email = payload.email.strip().lower()

    cutoff = datetime.now(UTC) - timedelta(minutes=LOGIN_RATE_LIMIT_WINDOW_MINUTES)
    recent_failures = (
        await session.execute(
            select(func.count())
            .select_from(LoginFailure)
            .where(LoginFailure.email == email, LoginFailure.attempted_at > cutoff)
        )
    ).scalar_one()
    if recent_failures >= LOGIN_RATE_LIMIT_MAX_FAILURES:
        raise HTTPException(
            status_code=429, detail="Too many failed login attempts. Try again later."
        )

    user = (
        await session.execute(select(User).where(func.lower(User.email) == email))
    ).scalar_one_or_none()

    if user is not None and user.is_active:
        password_ok = verify_password(payload.password, user.password_hash)
    else:
        verify_password(payload.password, _DUMMY_PASSWORD_HASH)  # constant-time; result unused
        password_ok = False

    if not password_ok or user is None:
        session.add(LoginFailure(email=email))
        await session.commit()
        raise HTTPException(status_code=401, detail=GENERIC_LOGIN_ERROR)

    family_id = uuid.uuid4()
    raw_refresh_token = await _issue_refresh_token(session, user.id, family_id)
    await session.commit()

    _set_refresh_cookie(response, raw_refresh_token)
    return AccessTokenResponse(access_token=create_access_token(user.id))


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> AccessTokenResponse:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    stored = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == _hash_refresh_token(raw_token))
        )
    ).scalar_one_or_none()

    if stored is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    now = datetime.now(UTC)

    if stored.revoked_at is not None or stored.expires_at < now:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Not authenticated")

    if stored.used_at is not None:
        # This token was already redeemed once before — presenting it again
        # is not a retry, it's proof the token leaked. Kill the whole chain.
        await _revoke_family(session, stored.family_id)
        await session.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Claim it atomically: if two requests race on the same not-yet-used
    # token, only one UPDATE matches a row (Postgres read-committed — the
    # loser's WHERE used_at IS NULL sees the winner's already-committed
    # write). The loser is treated exactly like reuse: from outside, a race
    # and theft look identical, and the family gets revoked either way.
    claim = cast(
        "CursorResult[Any]",
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.id == stored.id, RefreshToken.used_at.is_(None))
            .values(used_at=now)
        ),
    )
    if claim.rowcount == 0:
        await session.rollback()
        await _revoke_family(session, stored.family_id)
        await session.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Not authenticated")

    new_raw_token = await _issue_refresh_token(session, stored.user_id, stored.family_id)
    await session.commit()

    _set_refresh_cookie(response, new_raw_token)
    return AccessTokenResponse(access_token=create_access_token(stored.user_id))


@router.post("/logout", status_code=204)
async def logout(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> None:
    _clear_refresh_cookie(response)

    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token is None:
        return

    stored = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == _hash_refresh_token(raw_token))
        )
    ).scalar_one_or_none()
    if stored is None:
        return

    await _revoke_family(session, stored.family_id)
    await session.commit()


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.db import get_session
from wellness.models import User
from wellness.security import decode_access_token


@dataclass
class PageParams:
    limit: int
    offset: int


def page_params(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


# auto_error=False: a missing header should 401 with our own message below,
# not FastAPI's default HTTPBearer 403.
_bearer_scheme = HTTPBearer(auto_error=False)

def _unauthenticated() -> HTTPException:
    # A function, not a shared module-level instance: FastAPI handlers run
    # concurrently on one event loop, and raise() mutates __traceback__ on
    # the exception object — sharing one instance across concurrent
    # requests risks that mutation racing across requests.
    return HTTPException(status_code=401, detail="Not authenticated")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Available to any router that wants to require a logged-in user — not
    applied anywhere yet. Rejects the same way (401, same message) whether
    the header is missing, the token is malformed/expired/wrongly signed,
    or the token is valid but the account it names is gone or deactivated —
    none of those are a caller's business to distinguish.
    """
    if credentials is None:
        raise _unauthenticated()

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _unauthenticated()

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthenticated()

    return user

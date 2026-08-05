# Smoke-test endpoints only — no auth. Anyone who can reach this router can
# read/write any user, including creating accounts and changing passwords.
# TODO: add real authentication/authorization before this is exposed beyond
# local smoke testing.

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import User
from wellness.schemas.users import UserCreate, UserRead, UserUpdate
from wellness.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=201)
async def create_user(payload: UserCreate, session: AsyncSession = Depends(get_session)) -> User:
    data = payload.model_dump(exclude={"password"})
    user = User(**data, password_hash=hash_password(payload.password))
    session.add(user)
    await commit_or_409(session)
    await session.refresh(user)
    return user


@router.get("", response_model=list[UserRead])
async def list_users(
    pagination: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    result = await session.execute(
        select(User).order_by(User.created_at.desc()).limit(pagination.limit).offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise not_found("user")
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID, payload: UserUpdate, session: AsyncSession = Depends(get_session)
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise not_found("user")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))
    for key, value in data.items():
        setattr(user, key, value)
    await commit_or_409(session)
    await session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise not_found("user")
    await session.delete(user)
    await commit_or_409(session)

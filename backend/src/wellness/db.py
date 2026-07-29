from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from wellness.config import get_settings

_engine: AsyncEngine = create_async_engine(
    get_settings().sqlalchemy_database_url(), pool_pre_ping=True
)

_session_factory = async_sessionmaker(bind=_engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as session:
        yield session

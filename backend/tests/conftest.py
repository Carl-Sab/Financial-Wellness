"""Session-wide test setup.

wellness.db builds its async engine at *import time* from
wellness.config.get_settings() (which is @lru_cache'd), so the Postgres
container has to be up and DATABASE_URL has to be set before anything in the
wellness package is imported for the first time anywhere in the process —
including by pytest's test collection. That's why this happens at conftest
module level rather than inside a fixture: fixtures only run once a test
actually needs them, but collection (importing test files) happens first,
and a test file doing `from wellness.main import app` at module scope would
otherwise build the engine against whatever DATABASE_URL (or its absence)
happened to be in the environment at that point.
"""

import os
import uuid
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from testcontainers.community.postgres import PostgresContainer

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_BACKEND_ROOT = Path(__file__).resolve().parent.parent

_postgres = PostgresContainer("postgres:16", driver="asyncpg")
_postgres.start()
os.environ["DATABASE_URL"] = _postgres.get_connection_url()

_alembic_cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
command.upgrade(_alembic_cfg, "head")


def pytest_sessionfinish(*_: Any) -> None:
    _postgres.stop()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # Imported lazily: only safe once the module-level setup above has run.
    from wellness.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def unique() -> Callable[[str], str]:
    """A collision-free value for fields with a UNIQUE constraint (email,
    account_number), so tests can run repeatedly against the same container
    without deleting their own fixture data first.
    """

    def _unique(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    return _unique


@pytest_asyncio.fixture
async def user_id(client: AsyncClient, unique: Callable[[str], str]) -> str:
    """A user created through the API, for tests of resources that FK to it."""
    resp = await client.post(
        "/api/v1/users",
        json={
            "full_name": "Fixture User",
            "email": f"{unique('fixture')}@example.com",
            "password": "hunter2pass",
            "date_of_birth": "1990-01-01",
        },
    )
    assert resp.status_code == 201
    created_id: str = resp.json()["id"]
    return created_id


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator["AsyncSession"]:
    """Direct DB access for the handful of things the API has no CRUD for
    (financial_profile has no router — it was out of scope for the CRUD
    task — but the budget-fallback tests need to create one).
    """
    from wellness.db import get_session

    async for session in get_session():
        yield session


@pytest_asyncio.fixture
async def bank_account_id(client: AsyncClient, user_id: str, unique: Callable[[str], str]) -> int:
    """A bank account created through the API, for bank_ledger tests."""
    resp = await client.post(
        "/api/v1/bank-accounts",
        json={"user_id": user_id, "account_number": unique("ACC")},
    )
    assert resp.status_code == 201
    created_id: int = resp.json()["id"]
    return created_id

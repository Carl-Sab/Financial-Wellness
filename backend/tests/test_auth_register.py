"""Integration tests for POST /api/v1/auth/register — the real signup entry
point, distinct from the smoke-test CRUD at POST /api/v1/users (see
test_users.py). Covers the transactional user+user_settings creation, the
three server-side validations the client-side form can't be trusted to
enforce, and that the plaintext password never round-trips in a response.
"""

from collections.abc import Callable
from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.models import BankAccount, BankLedger, User, UserSettings


def _payload(unique: Callable[[str], str], **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "full_name": "Ada Lovelace",
        "email": f"{unique('ada')}@example.com",
        "password": "hunter2pass",
        "date_of_birth": "1990-01-01",
    }
    base.update(overrides)
    return base


async def test_register_creates_user_and_default_settings_in_one_go(
    client: AsyncClient, unique: Callable[[str], str], db_session: AsyncSession
) -> None:
    resp = await client.post("/api/v1/auth/register", json=_payload(unique))
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert "password_hash" not in body
    assert "password" not in body
    assert body["full_name"] == "Ada Lovelace"
    assert body["timezone"] == "Asia/Beirut"
    assert body["currency"] == "LBP"

    settings_row = await db_session.get(UserSettings, body["id"])
    assert settings_row is not None


async def test_register_creates_bank_account_with_no_ledger_entries(
    client: AsyncClient, unique: Callable[[str], str], db_session: AsyncSession
) -> None:
    resp = await client.post(
        "/api/v1/auth/register", json=_payload(unique, currency="USD")
    )
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["id"]

    account = (
        await db_session.execute(select(BankAccount).where(BankAccount.user_id == user_id))
    ).scalar_one_or_none()
    assert account is not None
    assert account.currency == "USD"
    assert account.is_active is True
    assert account.account_number

    ledger_rows = (
        await db_session.execute(select(BankLedger).where(BankLedger.account_id == account.id))
    ).scalars().all()
    assert ledger_rows == []


async def test_register_response_never_contains_plaintext_password(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    resp = await client.post("/api/v1/auth/register", json=_payload(unique, password="hunter2pass"))
    assert resp.status_code == 201, resp.text
    assert "hunter2pass" not in resp.text


async def test_password_hash_is_not_the_plaintext_password(
    client: AsyncClient, unique: Callable[[str], str], db_session: AsyncSession
) -> None:
    resp = await client.post("/api/v1/auth/register", json=_payload(unique, password="hunter2pass"))
    user = await db_session.get(User, resp.json()["id"])
    assert user is not None
    assert user.password_hash != "hunter2pass"
    assert "hunter2pass" not in user.password_hash


async def test_duplicate_email_returns_409(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    payload = _payload(unique)
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201, first.text

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_invalid_email_format_returns_422(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    resp = await client.post("/api/v1/auth/register", json=_payload(unique, email="not-an-email"))
    assert resp.status_code == 422


async def test_password_under_8_chars_returns_422(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    resp = await client.post("/api/v1/auth/register", json=_payload(unique, password="short1"))
    assert resp.status_code == 422


async def test_short_password_never_appears_in_the_422_response(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    resp = await client.post("/api/v1/auth/register", json=_payload(unique, password="short1"))
    assert resp.status_code == 422
    assert "short1" not in resp.text


async def test_under_13_date_of_birth_returns_422(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    twelve_years_ago = date.today().replace(year=date.today().year - 12).isoformat()
    resp = await client.post(
        "/api/v1/auth/register", json=_payload(unique, date_of_birth=twelve_years_ago)
    )
    assert resp.status_code == 422


async def test_exactly_13_years_old_succeeds(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    thirteen_years_ago = date.today().replace(year=date.today().year - 13).isoformat()
    resp = await client.post(
        "/api/v1/auth/register", json=_payload(unique, date_of_birth=thirteen_years_ago)
    )
    assert resp.status_code == 201, resp.text


async def test_missing_required_field_returns_422(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    payload = _payload(unique)
    del payload["full_name"]
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422


async def test_optional_fields_are_stored_when_provided(
    client: AsyncClient, unique: Callable[[str], str]
) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json=_payload(
            unique,
            phone="+961 71 234 567",
            address="Rue Gouraud",
            city="Beirut",
            country="Lebanon",
            timezone="Europe/London",
            currency="USD",
        ),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["phone"] == "+961 71 234 567"
    assert body["city"] == "Beirut"
    assert body["country"] == "Lebanon"
    assert body["timezone"] == "Europe/London"
    assert body["currency"] == "USD"


async def test_rollback_on_failure_leaves_no_orphaned_user(
    client: AsyncClient, unique: Callable[[str], str], db_session: AsyncSession
) -> None:
    """A user created via one email, then a second register attempt reusing
    it fails with 409 — the failed attempt must not leave a second users
    row or a mismatched user_settings row behind.
    """
    email = f"{unique('dup')}@example.com"
    first = await client.post("/api/v1/auth/register", json=_payload(unique, email=email))
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=_payload(unique, email=email))
    assert second.status_code == 409

    count = (
        await db_session.execute(select(User).where(User.email == email))
    ).scalars().all()
    assert len(count) == 1

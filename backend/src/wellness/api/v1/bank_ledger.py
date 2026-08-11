# Ownership isn't a direct column here — bank_ledger has no user_id, only
# account_id — so every check below goes through BankAccount.user_id.

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, get_current_user, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import BankAccount, BankLedger, User
from wellness.schemas.banking import BankLedgerCreate, BankLedgerRead, BankLedgerUpdate

router = APIRouter(prefix="/bank-ledger", tags=["bank_ledger"])


@router.post("", response_model=BankLedgerRead, status_code=201)
async def create_bank_ledger_entry(
    payload: BankLedgerCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BankLedger:
    account = await session.get(BankAccount, payload.account_id)
    if account is None or account.user_id != current_user.id:
        # The account this entry would belong to either doesn't exist or
        # isn't the caller's — 404 either way, not 403, so this can't be
        # used to probe whether some other account_id exists.
        raise not_found("bank_account")

    entry = BankLedger(**payload.model_dump())
    session.add(entry)
    await commit_or_409(session)
    await session.refresh(entry)
    return entry


@router.get("", response_model=list[BankLedgerRead])
async def list_bank_ledger_entries(
    pagination: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[BankLedger]:
    result = await session.execute(
        select(BankLedger)
        .join(BankAccount, BankLedger.account_id == BankAccount.id)
        .where(BankAccount.user_id == current_user.id)
        .order_by(BankLedger.occurred_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


async def _owned_entry(
    session: AsyncSession, entry_id: int, current_user_id: object
) -> BankLedger | None:
    result = await session.execute(
        select(BankLedger)
        .join(BankAccount, BankLedger.account_id == BankAccount.id)
        .where(BankLedger.id == entry_id, BankAccount.user_id == current_user_id)
    )
    return result.scalar_one_or_none()


@router.get("/{entry_id}", response_model=BankLedgerRead)
async def get_bank_ledger_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BankLedger:
    entry = await _owned_entry(session, entry_id, current_user.id)
    if entry is None:
        raise not_found("bank_ledger_entry")
    return entry


@router.patch("/{entry_id}", response_model=BankLedgerRead)
async def update_bank_ledger_entry(
    entry_id: int,
    payload: BankLedgerUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BankLedger:
    entry = await _owned_entry(session, entry_id, current_user.id)
    if entry is None:
        raise not_found("bank_ledger_entry")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    await commit_or_409(session)
    await session.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
async def delete_bank_ledger_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    entry = await _owned_entry(session, entry_id, current_user.id)
    if entry is None:
        raise not_found("bank_ledger_entry")
    await session.delete(entry)
    await commit_or_409(session)

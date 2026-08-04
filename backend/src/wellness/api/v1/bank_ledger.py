# Smoke-test endpoints only — no auth. TODO: add real authentication before
# this is exposed beyond local smoke testing.

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import BankLedger
from wellness.schemas.banking import BankLedgerCreate, BankLedgerRead, BankLedgerUpdate

router = APIRouter(prefix="/bank-ledger", tags=["bank_ledger"])


@router.post("", response_model=BankLedgerRead, status_code=201)
async def create_bank_ledger_entry(
    payload: BankLedgerCreate, session: AsyncSession = Depends(get_session)
) -> BankLedger:
    entry = BankLedger(**payload.model_dump())
    session.add(entry)
    await commit_or_409(session)
    await session.refresh(entry)
    return entry


@router.get("", response_model=list[BankLedgerRead])
async def list_bank_ledger_entries(
    pagination: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> list[BankLedger]:
    result = await session.execute(
        select(BankLedger)
        .order_by(BankLedger.occurred_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{entry_id}", response_model=BankLedgerRead)
async def get_bank_ledger_entry(
    entry_id: int, session: AsyncSession = Depends(get_session)
) -> BankLedger:
    entry = await session.get(BankLedger, entry_id)
    if entry is None:
        raise not_found("bank_ledger_entry")
    return entry


@router.patch("/{entry_id}", response_model=BankLedgerRead)
async def update_bank_ledger_entry(
    entry_id: int, payload: BankLedgerUpdate, session: AsyncSession = Depends(get_session)
) -> BankLedger:
    entry = await session.get(BankLedger, entry_id)
    if entry is None:
        raise not_found("bank_ledger_entry")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    await commit_or_409(session)
    await session.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
async def delete_bank_ledger_entry(
    entry_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    entry = await session.get(BankLedger, entry_id)
    if entry is None:
        raise not_found("bank_ledger_entry")
    await session.delete(entry)
    await commit_or_409(session)

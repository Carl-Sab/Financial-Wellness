# Smoke-test endpoints only — no auth. TODO: add real authentication before
# this is exposed beyond local smoke testing.

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import Transaction
from wellness.schemas.transactions import TransactionCreate, TransactionRead, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("", response_model=TransactionRead, status_code=201)
async def create_transaction(
    payload: TransactionCreate, session: AsyncSession = Depends(get_session)
) -> Transaction:
    data = payload.model_dump(exclude_unset=True)
    transaction = Transaction(**data)
    session.add(transaction)
    await commit_or_409(session)
    await session.refresh(transaction)
    return transaction


@router.get("", response_model=list[TransactionRead])
async def list_transactions(
    pagination: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> list[Transaction]:
    result = await session.execute(
        select(Transaction)
        .order_by(Transaction.occurred_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{transaction_id}", response_model=TransactionRead)
async def get_transaction(
    transaction_id: int, session: AsyncSession = Depends(get_session)
) -> Transaction:
    transaction = await session.get(Transaction, transaction_id)
    if transaction is None:
        raise not_found("transaction")
    return transaction


@router.patch("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    session: AsyncSession = Depends(get_session),
) -> Transaction:
    transaction = await session.get(Transaction, transaction_id)
    if transaction is None:
        raise not_found("transaction")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(transaction, key, value)
    await commit_or_409(session)
    await session.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    transaction = await session.get(Transaction, transaction_id)
    if transaction is None:
        raise not_found("transaction")
    await session.delete(transaction)
    await commit_or_409(session)

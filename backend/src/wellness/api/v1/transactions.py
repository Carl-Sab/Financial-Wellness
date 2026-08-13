from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, get_current_user, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import BankAccount, Checkin, Transaction, User
from wellness.schemas.transactions import TransactionCreate, TransactionRead, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


async def _owned_account(
    session: AsyncSession, user_id: object, account_id: int | None
) -> BankAccount:
    query = select(BankAccount).where(
        BankAccount.user_id == user_id,
        BankAccount.is_active.is_(True),
    )
    if account_id is None:
        query = query.order_by(BankAccount.opened_at, BankAccount.id).limit(1)
    else:
        query = query.where(BankAccount.id == account_id)

    account = (await session.execute(query)).scalar_one_or_none()
    if account is None:
        raise not_found("active_bank_account")
    return account


async def _validate_owned_checkin(
    session: AsyncSession, user_id: object, checkin_id: int | None
) -> None:
    if checkin_id is None:
        return
    checkin = await session.get(Checkin, checkin_id)
    if checkin is None or checkin.user_id != user_id:
        raise not_found("checkin")


@router.post("", response_model=TransactionRead, status_code=201)
async def create_transaction(
    payload: TransactionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Transaction:
    account = await _owned_account(session, current_user.id, payload.account_id)
    await _validate_owned_checkin(session, current_user.id, payload.checkin_id)

    data = payload.model_dump(exclude_unset=True)
    data["account_id"] = account.id
    data["currency"] = payload.currency or account.currency
    if data.get("occurred_at") is None:
        data.pop("occurred_at", None)

    transaction = Transaction(**data, user_id=current_user.id)
    session.add(transaction)
    await commit_or_409(session)
    await session.refresh(transaction)
    return transaction


@router.get("", response_model=list[TransactionRead])
async def list_transactions(
    pagination: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Transaction]:
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.occurred_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{transaction_id}", response_model=TransactionRead)
async def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Transaction:
    transaction = await session.get(Transaction, transaction_id)
    if transaction is None or transaction.user_id != current_user.id:
        raise not_found("transaction")
    return transaction


@router.patch("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Transaction:
    transaction = await session.get(Transaction, transaction_id)
    if transaction is None or transaction.user_id != current_user.id:
        raise not_found("transaction")

    fields = payload.model_fields_set
    required_if_present = ("account_id", "direction", "amount", "currency", "occurred_at")
    for field in required_if_present:
        if field in fields and getattr(payload, field) is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")

    if "account_id" in fields:
        account = await _owned_account(session, current_user.id, payload.account_id)
        transaction.account_id = account.id
    if "checkin_id" in fields:
        await _validate_owned_checkin(session, current_user.id, payload.checkin_id)

    for key, value in payload.model_dump(exclude_unset=True, exclude={"account_id"}).items():
        setattr(transaction, key, value)
    await commit_or_409(session)
    await session.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    transaction = await session.get(Transaction, transaction_id)
    if transaction is None or transaction.user_id != current_user.id:
        raise not_found("transaction")
    await session.delete(transaction)
    await commit_or_409(session)

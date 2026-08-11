# No balance column exists anywhere — /balance below always recomputes it by
# summing bank_ledger. See the boundary comment in wellness.models.banking.

from fastapi import APIRouter, Depends
from sqlalchemy import case, select
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.api.deps import PageParams, get_current_user, page_params
from wellness.api.errors import commit_or_409, not_found
from wellness.db import get_session
from wellness.models import BankAccount, BankLedger, User
from wellness.models.enums import LedgerDirection
from wellness.schemas.banking import (
    BankAccountBalance,
    BankAccountCreate,
    BankAccountRead,
    BankAccountUpdate,
)

router = APIRouter(prefix="/bank-accounts", tags=["bank_accounts"])


@router.post("", response_model=BankAccountRead, status_code=201)
async def create_bank_account(
    payload: BankAccountCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BankAccount:
    account = BankAccount(**payload.model_dump(), user_id=current_user.id)
    session.add(account)
    await commit_or_409(session)
    await session.refresh(account)
    return account


@router.get("", response_model=list[BankAccountRead])
async def list_bank_accounts(
    pagination: PageParams = Depends(page_params),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[BankAccount]:
    result = await session.execute(
        select(BankAccount)
        .where(BankAccount.user_id == current_user.id)
        .order_by(BankAccount.opened_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return list(result.scalars().all())


@router.get("/{account_id}", response_model=BankAccountRead)
async def get_bank_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BankAccount:
    account = await session.get(BankAccount, account_id)
    if account is None or account.user_id != current_user.id:
        raise not_found("bank_account")
    return account


@router.patch("/{account_id}", response_model=BankAccountRead)
async def update_bank_account(
    account_id: int,
    payload: BankAccountUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BankAccount:
    account = await session.get(BankAccount, account_id)
    if account is None or account.user_id != current_user.id:
        raise not_found("bank_account")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    await commit_or_409(session)
    await session.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
async def delete_bank_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    account = await session.get(BankAccount, account_id)
    if account is None or account.user_id != current_user.id:
        raise not_found("bank_account")
    await session.delete(account)
    await commit_or_409(session)


@router.get("/{account_id}/balance", response_model=BankAccountBalance)
async def get_bank_account_balance(
    account_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BankAccountBalance:
    account = await session.get(BankAccount, account_id)
    if account is None or account.user_id != current_user.id:
        raise not_found("bank_account")

    signed_amount = sa_func.sum(
        case(
            (BankLedger.direction == LedgerDirection.CREDIT, BankLedger.amount),
            else_=-BankLedger.amount,
        )
    )
    query = select(sa_func.coalesce(signed_amount, 0)).where(BankLedger.account_id == account_id)
    balance = (await session.execute(query)).scalar_one()
    return BankAccountBalance(account_id=account_id, balance=balance)

"""Create repeatable demo accounts with long, distinct chart histories.

The script only replaces the four accounts listed in DEMO_ACCOUNTS. It does
not touch any other user. Run from the backend container with:

    python scripts/seed_correlation_demo_accounts.py
"""

from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.db import get_session
from wellness.models import (
    BankAccount,
    Checkin,
    FinancialProfile,
    LoginFailure,
    NotificationFeedback,
    NotificationOutbox,
    QuestionnaireResponse,
    RefreshToken,
    Transaction,
    User,
    UserGoal,
    UserNormalizationSnapshot,
)
from wellness.models.enums import TransactionDirection, ValenceLevel
from wellness.models.normalization_snapshots import POPULATION_NORMALIZATION_DEFAULTS
from wellness.security import hash_password

MONEY = Decimal("0.01")
MONTHLY_BUDGET = Decimal("90000000.00")
HISTORY_DAYS = 420
CATEGORY_CODES = (
    "groceries",
    "restaurant",
    "clothing",
    "online",
    "electronics",
    "mall",
    "other",
)
VALENCES = (
    ValenceLevel.VERY_UNPLEASANT,
    ValenceLevel.UNPLEASANT,
    ValenceLevel.NEUTRAL,
    ValenceLevel.PLEASANT,
    ValenceLevel.VERY_PLEASANT,
)


@dataclass(frozen=True)
class DemoAccount:
    email: str
    password: str
    full_name: str
    account_number: str
    pattern: str
    seed: int


DEMO_ACCOUNTS = (
    DemoAccount(
        email="demo.nopattern@example.com",
        password="DemoNoPattern!2026",
        full_name="Demo No Pattern",
        account_number="DEMO-NO-PATTERN-2026",
        pattern="no_pattern",
        seed=1101,
    ),
    DemoAccount(
        email="demo.mood@example.com",
        password="DemoMoodPattern!2026",
        full_name="Demo Mood Pattern",
        account_number="DEMO-MOOD-2026",
        pattern="mood",
        seed=2202,
    ),
    DemoAccount(
        email="demo.arousal@example.com",
        password="DemoArousalPattern!2026",
        full_name="Demo Arousal Pattern",
        account_number="DEMO-AROUSAL-2026",
        pattern="arousal",
        seed=3303,
    ),
    DemoAccount(
        email="demo.mixed@example.com",
        password="DemoMixedPattern!2026",
        full_name="Demo Mixed Pattern",
        account_number="DEMO-MIXED-2026",
        pattern="mixed",
        seed=4404,
    ),
)


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _daily_signals(
    account: DemoAccount, day_index: int, signal_random: random.Random
) -> tuple[ValenceLevel, int]:
    if account.pattern == "mood":
        return VALENCES[day_index % len(VALENCES)], signal_random.choice([-2, -1, 0, 1, 2])
    if account.pattern == "arousal":
        return signal_random.choice(VALENCES), (-2, -1, 0, 1, 2)[day_index % 5]
    return signal_random.choice(VALENCES), signal_random.choice([-2, -1, 0, 1, 2])


def _daily_spend(
    account: DemoAccount,
    valence: ValenceLevel,
    arousal: int,
    spend_random: random.Random,
) -> Decimal:
    valence_number = VALENCES.index(valence) - 2
    noise = spend_random.uniform(-180_000, 180_000)
    if account.pattern == "mood":
        value = 1_650_000 + (valence_number + 2) * 720_000 + noise
    elif account.pattern == "arousal":
        value = 1_650_000 + (arousal + 2) * 720_000 + noise
    elif account.pattern == "mixed":
        negative_mood = max(-valence_number, 0)
        value = (
            2_000_000
            + negative_mood * 650_000
            + (arousal + 2) * 230_000
            + noise
        )
    else:
        value = spend_random.uniform(1_300_000, 4_800_000)
    return _money(max(value, 250_000))


async def _existing_user_id(session: AsyncSession, email: str) -> uuid.UUID | None:
    result = await session.execute(select(User.id).where(User.email == email))
    return result.scalar_one_or_none()


async def _remove_demo_user(
    session: AsyncSession, user_id: uuid.UUID, email: str
) -> None:
    outbox_ids = (
        await session.execute(
            select(NotificationOutbox.id).where(NotificationOutbox.user_id == user_id)
        )
    ).scalars().all()
    if outbox_ids:
        await session.execute(
            delete(NotificationFeedback).where(
                NotificationFeedback.outbox_id.in_(outbox_ids)
            )
        )
    await session.execute(
        delete(NotificationOutbox).where(NotificationOutbox.user_id == user_id)
    )
    await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await session.execute(delete(Checkin).where(Checkin.user_id == user_id))
    await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await session.execute(delete(BankAccount).where(BankAccount.user_id == user_id))
    await session.execute(delete(UserGoal).where(UserGoal.user_id == user_id))
    await session.execute(
        delete(FinancialProfile).where(FinancialProfile.user_id == user_id)
    )
    await session.execute(
        delete(QuestionnaireResponse).where(QuestionnaireResponse.user_id == user_id)
    )
    await session.execute(
        delete(UserNormalizationSnapshot).where(
            UserNormalizationSnapshot.user_id == user_id
        )
    )
    await session.execute(delete(User).where(User.id == user_id))
    await session.execute(delete(LoginFailure).where(LoginFailure.email == email))
    await session.commit()


def _questionnaire(account: DemoAccount, start_date: date) -> QuestionnaireResponse:
    scores = {
        "no_pattern": (2.4, 3.7, 3.8, 4.8, 3.6),
        "mood": (3.6, 2.8, 5.4, 3.5, 2.9),
        "arousal": (3.0, 3.1, 4.7, 4.1, 3.2),
        "mixed": (3.8, 2.6, 5.6, 3.2, 2.7),
    }[account.pattern]
    return QuestionnaireResponse(
        impulse_tendency_score=scores[0],
        self_control_score=scores[1],
        hedonic_score=scores[2],
        utilitarian_score=scores[3],
        normative_eval_score=scores[4],
        raw_responses={"seeded_demo_profile": account.pattern},
        completed_at=datetime.combine(start_date, time(9), tzinfo=UTC),
    )


async def _seed_account(
    session: AsyncSession, account: DemoAccount, start_date: date, end_date: date
) -> tuple[int, int]:
    user = User(
        full_name=account.full_name,
        email=account.email,
        password_hash=hash_password(account.password),
        date_of_birth=date(1992, 5, 14),
        phone="+961 70 000 000",
        address="Demo account",
        city="Beirut",
        country="Lebanon",
        timezone="Asia/Beirut",
        currency="LBP",
    )
    session.add(user)
    await session.flush()

    bank_account = BankAccount(
        user_id=user.id,
        account_number=account.account_number,
        currency="LBP",
        opening_balance=Decimal("250000000.00"),
        opened_at=datetime.combine(start_date, time(8), tzinfo=UTC),
    )
    session.add(bank_account)
    await session.flush()

    questionnaire = _questionnaire(account, start_date)
    questionnaire.user_id = user.id
    session.add(questionnaire)
    session.add(
        UserNormalizationSnapshot(
            user_id=user.id,
            recorded_at=datetime.combine(start_date, time(8, 30), tzinfo=UTC),
            **POPULATION_NORMALIZATION_DEFAULTS,
        )
    )
    session.add(
        UserGoal(
            user_id=user.id,
            goal_type="monthly_budget",
            category_code=None,
            target_amount=MONTHLY_BUDGET,
            currency="LBP",
            period="monthly",
            starts_on=start_date,
            is_active=True,
        )
    )

    signal_random = random.Random(account.seed)
    spend_random = random.Random(account.seed + 99_991)
    checkins: list[Checkin] = []
    daily_specs: list[tuple[date, Decimal, str, str]] = []
    cursor = start_date
    day_index = 0
    while cursor <= end_date:
        valence, arousal = _daily_signals(account, day_index, signal_random)
        daily_total = _daily_spend(account, valence, arousal, spend_random)
        first_category = CATEGORY_CODES[day_index % len(CATEGORY_CODES)]
        second_category = CATEGORY_CODES[(day_index * 3 + 2) % len(CATEGORY_CODES)]
        for hour, category_code in ((9, first_category), (17, second_category)):
            checkin = Checkin(
                user_id=user.id,
                category_code=category_code,
                valence=valence,
                arousal_input_mode="manual",
                arousal_z=arousal,
                entered_at=datetime.combine(cursor, time(hour), tzinfo=UTC),
            )
            session.add(checkin)
            checkins.append(checkin)
        daily_specs.append((cursor, daily_total, first_category, second_category))
        cursor += timedelta(days=1)
        day_index += 1
    await session.flush()

    transactions: list[Transaction] = []
    for day_offset, (day, total, first_category, second_category) in enumerate(daily_specs):
        first_amount = _money(total * Decimal("0.58"))
        second_amount = total - first_amount
        first_checkin = checkins[day_offset * 2]
        second_checkin = checkins[day_offset * 2 + 1]
        transactions.extend(
            (
                Transaction(
                    user_id=user.id,
                    account_id=bank_account.id,
                    checkin_id=first_checkin.id,
                    direction=TransactionDirection.DEBIT,
                    amount=first_amount,
                    currency="LBP",
                    category_code=first_category,
                    description="Seeded checked-in purchase",
                    occurred_at=datetime.combine(day, time(10), tzinfo=UTC),
                ),
                Transaction(
                    user_id=user.id,
                    account_id=bank_account.id,
                    checkin_id=second_checkin.id,
                    direction=TransactionDirection.DEBIT,
                    amount=second_amount,
                    currency="LBP",
                    category_code=second_category,
                    description="Seeded checked-in purchase",
                    occurred_at=datetime.combine(day, time(18), tzinfo=UTC),
                ),
            )
        )

    monthly_income = Decimal("125000000.00")
    month_cursor = start_date.replace(day=1)
    while month_cursor <= end_date:
        salary_day = max(month_cursor, start_date)
        transactions.append(
            Transaction(
                user_id=user.id,
                account_id=bank_account.id,
                direction=TransactionDirection.CREDIT,
                amount=monthly_income,
                currency="LBP",
                category_code=None,
                description="Monthly salary",
                occurred_at=datetime.combine(salary_day, time(8), tzinfo=UTC),
            )
        )
        month_cursor = (month_cursor.replace(day=28) + timedelta(days=4)).replace(day=1)

    session.add_all(transactions)
    average_monthly_spend = _money(
        sum((spec[1] for spec in daily_specs), Decimal("0"))
        * Decimal("30")
        / Decimal(len(daily_specs))
    )
    session.add(
        FinancialProfile(
            user_id=user.id,
            monthly_income=monthly_income,
            avg_monthly_spend=average_monthly_spend,
            currency="LBP",
            valid_from=datetime.combine(start_date, time.min, tzinfo=UTC),
        )
    )
    await session.commit()
    return len(checkins), len(transactions)


async def run() -> None:
    end_date = date.today()
    start_date = end_date - timedelta(days=HISTORY_DAYS - 1)
    async for session in get_session():
        print(f"Seeding demo history from {start_date} through {end_date}...")
        for account in DEMO_ACCOUNTS:
            existing_id = await _existing_user_id(session, account.email)
            if existing_id is not None:
                await _remove_demo_user(session, existing_id, account.email)
            checkin_count, transaction_count = await _seed_account(
                session, account, start_date, end_date
            )
            print(
                f"  {account.email}: {checkin_count} check-ins, "
                f"{transaction_count} transactions"
            )
        break

    print("\nDemo credentials:")
    for account in DEMO_ACCOUNTS:
        print(f"  {account.email}  /  {account.password}")


if __name__ == "__main__":
    asyncio.run(run())

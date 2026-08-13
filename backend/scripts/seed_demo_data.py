"""Seed a complete demo user for the frontend and spending analysis.

Idempotent: if --user-email already exists, its data is wiped and regenerated
rather than duplicated. Deterministic: the RNG is seeded, so reruns with the
same arguments produce the same data.

Check-ins use the same normalized subjective values as the live UI. No wearable
samples or per-user physiological baselines are generated.

Usage:
    uv run python scripts/seed_demo_data.py [--user-email demo@example.com] [--days 60]
    uv run python scripts/seed_demo_data.py --clean [--user-email demo@example.com]
"""

import argparse
import asyncio
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wellness.db import get_session
from wellness.models import (
    BankAccount,
    Checkin,
    FinancialProfile,
    NotificationFeedback,
    NotificationOutbox,
    QuestionnaireResponse,
    Transaction,
    User,
    UserGoal,
)
from wellness.models.enums import TransactionDirection, ValenceLevel
from wellness.security import hash_password
from wellness.services.analysis import get_mood_spending_analysis
from wellness.services.questionnaire_scoring import (
    BLOCK_E_NORM,
    raw_responses_with_polarity,
    score_block,
)

SEED = 20260810

STRESS_FRACTION = 0.4  # share of check-ins deliberately placed in a stress episode

DISCRETIONARY_CATEGORIES = {"clothing", "mall", "online"}

# (low, high) LBP per transaction, before the stressed-discretionary bump.
BASE_AMOUNT_RANGE_LBP: dict[str, tuple[float, float]] = {
    "groceries": (500_000, 1_400_000),
    "restaurant": (350_000, 1_000_000),
    "electronics": (1_500_000, 6_000_000),
    "clothing": (600_000, 1_800_000),
    "mall": (800_000, 2_500_000),
    "online": (300_000, 1_500_000),
    "other": (150_000, 700_000),
}

STRESS_CATEGORY_CHOICES = ["clothing", "mall", "online"]
STRESS_CATEGORY_WEIGHTS = [0.40, 0.35, 0.25]
STRESS_VALENCE_CHOICES = [ValenceLevel.UNPLEASANT, ValenceLevel.VERY_UNPLEASANT]
STRESS_VALENCE_WEIGHTS = [0.65, 0.35]

CALM_CATEGORY_CHOICES = [
    "groceries", "restaurant", "electronics", "other", "clothing", "mall", "online",
]
CALM_CATEGORY_WEIGHTS = [0.30, 0.25, 0.10, 0.10, 0.10, 0.10, 0.05]
CALM_VALENCE_CHOICES = [ValenceLevel.NEUTRAL, ValenceLevel.PLEASANT, ValenceLevel.VERY_PLEASANT]
CALM_VALENCE_WEIGHTS = [0.45, 0.35, 0.20]

STANDALONE_CATEGORY_CHOICES = ["groceries", "restaurant", "electronics", "other"]
STANDALONE_CATEGORY_WEIGHTS = [0.40, 0.30, 0.15, 0.15]


@dataclass
class StressEpisode:
    """A 30-90 minute elevated-arousal stretch."""

    start: datetime
    end: datetime


def _money(value: float) -> Decimal:
    return Decimal(round(value))


def _episode_at(episodes: list[StressEpisode], ts: datetime) -> StressEpisode | None:
    for episode in episodes:
        if episode.start <= ts <= episode.end:
            return episode
    return None


def _random_waking_timestamp(start_date: date, end_date: date) -> datetime:
    n_days = (end_date - start_date).days
    day = start_date + timedelta(days=random.randint(0, n_days))
    hour = random.uniform(7, 23)
    return datetime.combine(day, time(), tzinfo=UTC) + timedelta(hours=hour)


def _generate_episodes(start_date: date, end_date: date) -> list[StressEpisode]:
    n_days = (end_date - start_date).days + 1
    n_episodes = max(3, n_days // 5)
    episodes = []
    for _ in range(n_episodes):
        day = start_date + timedelta(days=random.randint(0, n_days - 1))
        start_hour = random.uniform(8, 21)
        start_dt = datetime.combine(day, time(), tzinfo=UTC) + timedelta(hours=start_hour)
        duration_minutes = random.uniform(30, 90)
        episodes.append(
            StressEpisode(
                start=start_dt,
                end=start_dt + timedelta(minutes=duration_minutes),
            )
        )
    episodes.sort(key=lambda e: e.start)
    return episodes


def _generate_checkin_specs(
    start_date: date, end_date: date, episodes: list[StressEpisode]
) -> list[tuple[datetime, str, ValenceLevel]]:
    """2-4 check-ins per week; ~STRESS_FRACTION of them dropped inside a
    stress episode (unpleasant valence, impulse-leaning category), the rest
    calm (neutral-to-pleasant valence, spread across all categories).
    """
    total_checkins = 0
    week_start = start_date
    while week_start <= end_date:
        total_checkins += random.randint(2, 4)
        week_start += timedelta(days=7)

    n_stress = round(total_checkins * STRESS_FRACTION)
    specs: list[tuple[datetime, str, ValenceLevel]] = []

    for _ in range(n_stress):
        episode = random.choice(episodes)
        span_minutes = max(1.0, (episode.end - episode.start).total_seconds() / 60)
        ts = episode.start + timedelta(minutes=random.uniform(0, span_minutes))
        category = random.choices(STRESS_CATEGORY_CHOICES, weights=STRESS_CATEGORY_WEIGHTS)[0]
        valence = random.choices(STRESS_VALENCE_CHOICES, weights=STRESS_VALENCE_WEIGHTS)[0]
        specs.append((ts, category, valence))

    for _ in range(total_checkins - n_stress):
        while True:
            ts = _random_waking_timestamp(start_date, end_date)
            if _episode_at(episodes, ts) is None:
                break
        category = random.choices(CALM_CATEGORY_CHOICES, weights=CALM_CATEGORY_WEIGHTS)[0]
        valence = random.choices(CALM_VALENCE_CHOICES, weights=CALM_VALENCE_WEIGHTS)[0]
        specs.append((ts, category, valence))

    specs.sort(key=lambda spec: spec[0])
    return specs


def _questionnaire_responses() -> dict[str, object]:
    impulse_items = [random.randint(1, 5) for _ in range(9)]
    self_control_items = [random.randint(1, 5) for _ in range(13)]
    hedonic_items = [random.randint(1, 7) for _ in range(11)]
    utilitarian_items = [random.randint(1, 7) for _ in range(4)]
    norm_items = [random.randint(1, 5) for _ in range(BLOCK_E_NORM.item_count)]

    raw: dict[str, object] = {
        **{f"impulse_{i + 1}": v for i, v in enumerate(impulse_items)},
        **{f"self_control_{i + 1}": v for i, v in enumerate(self_control_items)},
        **{f"hedonic_{i + 1}": v for i, v in enumerate(hedonic_items)},
        **{f"utilitarian_{i + 1}": v for i, v in enumerate(utilitarian_items)},
        **{f"norm_{i + 1}": v for i, v in enumerate(norm_items)},
    }
    # Block E's reverse-coding depends on which pairs have their favourable
    # adjective on the left — routed through the real scoring service
    # rather than duplicated here, so seed data can't silently drift from
    # what POST /api/v1/questionnaire actually computes.
    return {
        "impulse_tendency_score": round(sum(impulse_items) / len(impulse_items), 2),
        "self_control_score": round(sum(self_control_items) / len(self_control_items), 2),
        "hedonic_score": round(sum(hedonic_items) / len(hedonic_items), 2),
        "utilitarian_score": round(sum(utilitarian_items) / len(utilitarian_items), 2),
        "normative_eval_score": score_block(BLOCK_E_NORM, norm_items),
        "raw_responses": raw_responses_with_polarity(raw),
    }


def _transaction_amount(category_code: str, arousal_z: float | None) -> Decimal:
    low, high = BASE_AMOUNT_RANGE_LBP[category_code]
    amount = random.uniform(low, high)
    if category_code in DISCRETIONARY_CATEGORIES and arousal_z is not None and arousal_z >= 1:
        amount *= random.uniform(1.3, 1.5)
    return _money(amount)


def _pick_monthly_budget(daily_totals: dict[date, Decimal]) -> Decimal:
    """A budget a handful of the highest-spend days genuinely exceed, not
    something everything sails under or everything blows past.
    """
    totals_sorted = sorted(daily_totals.values(), reverse=True)
    k = max(3, min(8, len(totals_sorted) // 10))
    threshold = totals_sorted[k] if len(totals_sorted) > k else totals_sorted[-1] / 2
    return _money(float(threshold) * 30)


def _new_user(email: str, full_name: str) -> User:
    return User(
        full_name=full_name,
        email=email,
        password_hash=hash_password("demo-password-123"),
        date_of_birth=date(1992, 5, 14),
        phone="+961 71 234 567",
        address="Rue Gouraud",
        city="Beirut",
        country="Lebanon",
        timezone="Asia/Beirut",
        currency="LBP",
    )


async def _add_salary_transactions(
    session: AsyncSession,
    user: User,
    account: BankAccount,
    monthly_income: Decimal,
    start_date: date,
    end_date: date,
) -> None:
    salary_credits: list[Transaction] = []
    month_cursor = date(start_date.year, start_date.month, 1)
    while month_cursor <= end_date:
        credit_date = max(month_cursor, start_date)
        salary_credits.append(
            Transaction(
                user_id=user.id,
                account_id=account.id,
                direction=TransactionDirection.CREDIT,
                amount=monthly_income,
                currency=account.currency,
                category_code=None,
                description="Monthly salary",
                occurred_at=datetime.combine(credit_date, time(9, 0), tzinfo=UTC),
            )
        )
        month_cursor = (month_cursor.replace(day=28) + timedelta(days=4)).replace(day=1)

    session.add_all(salary_credits)
    await session.commit()


async def _find_user_id(session: AsyncSession, email: str) -> uuid.UUID | None:
    result = await session.execute(select(User.id).where(User.email == email))
    return result.scalar_one_or_none()


async def _wipe_user_data(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Deletes every row for this user, in FK-safe order (several FKs here
    have no ON DELETE action, so children must go before their parents).
    """
    outbox_ids = (
        await session.execute(
            select(NotificationOutbox.id).where(NotificationOutbox.user_id == user_id)
        )
    ).scalars().all()

    if outbox_ids:
        await session.execute(
            delete(NotificationFeedback).where(NotificationFeedback.outbox_id.in_(outbox_ids))
        )
    await session.execute(delete(NotificationOutbox).where(NotificationOutbox.user_id == user_id))
    await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await session.execute(delete(Checkin).where(Checkin.user_id == user_id))
    await session.execute(delete(BankAccount).where(BankAccount.user_id == user_id))
    await session.execute(delete(UserGoal).where(UserGoal.user_id == user_id))
    await session.execute(delete(FinancialProfile).where(FinancialProfile.user_id == user_id))
    await session.execute(
        delete(QuestionnaireResponse).where(QuestionnaireResponse.user_id == user_id)
    )
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()


async def _seed(session: AsyncSession, email: str, days: int) -> None:
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    user = _new_user(email, "Demo User")
    session.add(user)
    await session.flush()

    account = BankAccount(
        user_id=user.id,
        account_number=f"DEMO-{user.id.hex[:10].upper()}",
        currency="LBP",
    )
    session.add(account)
    await session.flush()

    session.add(
        QuestionnaireResponse(
            user_id=user.id,
            completed_at=datetime.combine(start_date, time(10, 0), tzinfo=UTC),
            **_questionnaire_responses(),
        )
    )
    await session.commit()

    episodes = _generate_episodes(start_date, end_date)
    checkin_specs = _generate_checkin_specs(start_date, end_date, episodes)

    checkins: list[Checkin] = []
    for ts, category_code, valence in checkin_specs:
        is_stress = _episode_at(episodes, ts) is not None
        checkin = Checkin(
            user_id=user.id,
            category_code=category_code,
            valence=valence,
            arousal_input_mode="manual",
            arousal_z=random.choice([1, 2]) if is_stress else random.choice([-1, 0, 1]),
            entered_at=ts,
        )
        session.add(checkin)
        checkins.append(checkin)
    await session.flush()

    transactions: list[Transaction] = []
    for checkin in checkins:
        amount = _transaction_amount(checkin.category_code, checkin.arousal_z)
        transactions.append(
            Transaction(
                user_id=user.id,
                account_id=account.id,
                checkin_id=checkin.id,
                direction=TransactionDirection.DEBIT,
                amount=amount,
                currency="LBP",
                category_code=checkin.category_code,
                occurred_at=checkin.entered_at + timedelta(minutes=random.uniform(2, 25)),
            )
        )

    n_standalone = max(1, days // 3)
    for _ in range(n_standalone):
        category_code = random.choices(
            STANDALONE_CATEGORY_CHOICES, weights=STANDALONE_CATEGORY_WEIGHTS
        )[0]
        transactions.append(
            Transaction(
                user_id=user.id,
                account_id=account.id,
                checkin_id=None,
                direction=TransactionDirection.DEBIT,
                amount=_transaction_amount(category_code, None),
                currency="LBP",
                category_code=category_code,
                occurred_at=_random_waking_timestamp(start_date, end_date),
            )
        )

    session.add_all(transactions)
    await session.flush()

    daily_totals: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for tx in transactions:
        daily_totals[tx.occurred_at.date()] += tx.amount

    monthly_target = _pick_monthly_budget(daily_totals)
    session.add(
        UserGoal(
            user_id=user.id,
            goal_type="monthly_budget",
            category_code=None,
            target_amount=monthly_target,
            period="monthly",
            starts_on=start_date,
            is_active=True,
        )
    )

    total_spend = sum((tx.amount for tx in transactions), Decimal("0"))
    avg_monthly_spend = _money(float(total_spend) / (days / 30))
    monthly_income = _money(float(avg_monthly_spend) * 1.4)

    session.add(
        FinancialProfile(
            user_id=user.id,
            monthly_income=monthly_income,
            avg_monthly_spend=avg_monthly_spend,
            currency="LBP",
            valid_from=datetime.combine(start_date, time(0, 0), tzinfo=UTC),
        )
    )
    await session.commit()

    await _add_salary_transactions(
        session, user, account, monthly_income, start_date, end_date
    )

    await _print_summary(session, user, start_date, end_date)


async def _count(session: AsyncSession, stmt: Select[tuple[int]]) -> int:
    result = await session.execute(stmt)
    return result.scalar_one()


async def _print_summary(
    session: AsyncSession, user: User, start_date: date, end_date: date
) -> None:
    row_counts = {
        "financial_profile": await _count(
            session, select(func.count()).select_from(FinancialProfile)
            .where(FinancialProfile.user_id == user.id)
        ),
        "questionnaire_responses": await _count(
            session, select(func.count()).select_from(QuestionnaireResponse)
            .where(QuestionnaireResponse.user_id == user.id)
        ),
        "checkins": await _count(
            session, select(func.count()).select_from(Checkin).where(Checkin.user_id == user.id)
        ),
        "transactions": await _count(
            session, select(func.count()).select_from(Transaction)
            .where(Transaction.user_id == user.id)
        ),
        "user_goals": await _count(
            session, select(func.count()).select_from(UserGoal).where(UserGoal.user_id == user.id)
        ),
        "bank_accounts": await _count(
            session, select(func.count()).select_from(BankAccount)
            .where(BankAccount.user_id == user.id)
        ),
        "account_credits": await _count(
            session,
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.user_id == user.id,
                Transaction.direction == TransactionDirection.CREDIT,
            ),
        ),
    }

    print(f"\n=== Demo data seeded for {user.email} ({user.id}) ===")
    print(f"Date range: {start_date} .. {end_date} ({(end_date - start_date).days + 1} days)\n")
    print("Row counts:")
    for table_name, count in row_counts.items():
        print(f"  {table_name:<24} {count}")

    analysis = await get_mood_spending_analysis(
        session, user.id, start_date, end_date, "month", user.currency
    )
    print(f"\nDaily budget: {analysis.daily_budget.amount} ({analysis.daily_budget.source})")
    print("\nMood-spending breakdown:")
    for period in analysis.periods:
        print(f"  {period.period_start} .. {period.period_end}")
        for bucket in period.buckets:
            print(
                f"    {bucket.mood:<12} n={bucket.transaction_count:<4} "
                f"overspend={bucket.overspend_count:<4} rate={bucket.overspend_rate:.2f} "
                f"avg={bucket.avg_amount:,.0f} total={bucket.total_amount:,.0f}"
            )


async def run(email: str, days: int, *, clean: bool) -> None:
    async for session in get_session():
        existing_id = await _find_user_id(session, email)

        if clean:
            if existing_id is None:
                print(f"No demo user found for {email}; nothing to clean.")
            else:
                await _wipe_user_data(session, existing_id)
                print(f"Removed demo user {email} ({existing_id}) and all associated data.")
            break

        if existing_id is not None:
            print(f"Existing demo user {email} ({existing_id}) found; wiping before regenerating.")
            await _wipe_user_data(session, existing_id)

        random.seed(SEED)
        await _seed(session, email, days)
        break


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-email",
        default=None,
        help="Defaults to demo@example.com.",
    )
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument(
        "--clean", action="store_true", help="Remove the demo user and all their data, then exit."
    )
    args = parser.parse_args()
    email = args.user_email or "demo@example.com"
    asyncio.run(run(email, args.days, clean=args.clean))


if __name__ == "__main__":
    main()

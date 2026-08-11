"""Seed a complete, realistic demo user so the frontend (charts, mood-spending
analysis) can be built and demoed without a real device or real data.

Idempotent: if --user-email already exists, its data is wiped and regenerated
rather than duplicated. Deterministic: the RNG is seeded, so reruns with the
same arguments produce the same data.

Everything physiological flows through the real services — refresh_baseline()
and score_checkin() — exactly as POST /checkins does. Nothing under
arousal_state is fabricated directly; if that pipeline has a bug, this seed
should surface it, not hide it. biometric_samples are inserted chronologically
interleaved with check-in scoring, never handed to refresh_baseline() ahead of
their own timestamp, so each check-in's baseline reflects only what a wearable
would actually have streamed by then — the same as live traffic sees it.

That interleaving alone will not show you the 'unknown' cold-start label,
though: samples arrive every 10 minutes, so the 30-sample source threshold
(see wellness.services.baseline.SAMPLE_SOURCE_MIN_N) is crossed within a few
waking hours, far faster than a realistic 2-4/week check-in cadence ever
catches it. The default run essentially never produces 'unknown'. Use
--cold-start for that: a separate, minimal user with a handful of check-ins
and zero biometric_samples, so every check-in scores 'unknown' on purpose.

Usage:
    uv run python scripts/seed_demo_data.py [--user-email demo@example.com] [--days 60]
    uv run python scripts/seed_demo_data.py --cold-start [--user-email cold-start@example.com]
    uv run python scripts/seed_demo_data.py --clean [--user-email demo@example.com]
"""

import argparse
import asyncio
import math
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
    ArousalState,
    BankAccount,
    BankLedger,
    BiometricSample,
    Checkin,
    FinancialProfile,
    NotificationFeedback,
    NotificationOutbox,
    QuestionnaireResponse,
    Transaction,
    User,
    UserBaseline,
    UserGoal,
    UserSettings,
)
from wellness.models.enums import ArousalLabel, LedgerDirection, ValenceLevel
from wellness.security import hash_password
from wellness.services.analysis import get_mood_spending_analysis
from wellness.services.arousal import score_checkin
from wellness.services.baseline import refresh_baseline
from wellness.services.questionnaire_scoring import (
    BLOCK_E_NORM,
    raw_responses_with_polarity,
    score_block,
)

SEED = 20260810

WAKE_START = time(7, 0)
WAKE_END = time(23, 0)
SAMPLE_INTERVAL_MINUTES = 10
STRESS_FRACTION = 0.4  # share of check-ins deliberately placed in a stress episode

COLD_START_EMAIL = "cold-start@example.com"
COLD_START_CHECKINS = 5
COLD_START_WINDOW_DAYS = 10

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

MERCHANTS: dict[str, list[str]] = {
    "groceries": ["Spinneys", "Carrefour", "TSC Le Charcutier"],
    "restaurant": ["Ahwak", "Em Sherif Cafe", "Roadster Diner"],
    "electronics": ["Khoury Home", "Batouty Computer", "Virgin Megastore"],
    "clothing": ["H&M", "Zara", "Mango"],
    "mall": ["ABC Achrafieh", "City Centre Beirut", "Beirut Souks"],
    "online": ["Amazon.ae", "Noon", "Shein"],
    "other": ["Corner Store", "Local Kiosk", "Misc. Purchase"],
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
    """A 30-90 minute elevated-arousal stretch: heart rate up, HRV down."""

    start: datetime
    end: datetime
    hr_boost: float
    hrv_drop: float
    spo2_drop: float


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _money(value: float) -> Decimal:
    return Decimal(round(value))


def _ambient_heart_rate(hour: float) -> float:
    """Low overnight, rising through the morning, peaking ~16:00."""
    return 68 + 9 * math.sin((hour - 10) / 24 * 2 * math.pi)


def _ambient_hrv(hour: float) -> float:
    """Mirrors heart rate: highest when HR is lowest, and vice versa."""
    return 52 - 6 * math.sin((hour - 10) / 24 * 2 * math.pi)


def _episode_at(episodes: list[StressEpisode], ts: datetime) -> StressEpisode | None:
    for episode in episodes:
        if episode.start <= ts <= episode.end:
            return episode
    return None


def _physio_reading(ts: datetime, episodes: list[StressEpisode]) -> tuple[float, float, float]:
    """(heart_rate, hrv_ms, spo2_percent) at `ts`, ambient or elevated, with noise."""
    hour = ts.hour + ts.minute / 60
    heart_rate = _ambient_heart_rate(hour)
    hrv_ms = _ambient_hrv(hour)
    spo2_percent = 97.5

    episode = _episode_at(episodes, ts)
    if episode is not None:
        heart_rate += episode.hr_boost
        hrv_ms -= episode.hrv_drop
        spo2_percent -= episode.spo2_drop

    heart_rate += random.gauss(0, 3)
    hrv_ms += random.gauss(0, 3.5)
    spo2_percent += random.gauss(0, 0.4)

    return (
        round(_clip(heart_rate, 40, 200), 1),
        round(_clip(hrv_ms, 15, 200), 1),
        round(_clip(spo2_percent, 90, 100), 1),
    )


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
                hr_boost=random.uniform(30, 50),
                hrv_drop=random.uniform(12, 22),
                spo2_drop=random.uniform(0.5, 2.0),
            )
        )
    episodes.sort(key=lambda e: e.start)
    return episodes


def _generate_biometric_samples(
    user_id: uuid.UUID, start_date: date, end_date: date, episodes: list[StressEpisode]
) -> list[BiometricSample]:
    samples = []
    day = start_date
    while day <= end_date:
        t = datetime.combine(day, WAKE_START, tzinfo=UTC)
        day_end = datetime.combine(day, WAKE_END, tzinfo=UTC)
        while t <= day_end:
            heart_rate, hrv_ms, spo2_percent = _physio_reading(t, episodes)
            samples.append(
                BiometricSample(
                    user_id=user_id, ts=t, heart_rate=heart_rate, hrv_ms=hrv_ms,
                    spo2_percent=spo2_percent,
                )
            )
            t += timedelta(minutes=SAMPLE_INTERVAL_MINUTES)
        day += timedelta(days=1)
    return samples


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


def _transaction_amount(category_code: str, label: ArousalLabel | None) -> Decimal:
    low, high = BASE_AMOUNT_RANGE_LBP[category_code]
    amount = random.uniform(low, high)
    if category_code in DISCRETIONARY_CATEGORIES and label == ArousalLabel.HIGH:
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


async def _create_bank_account_and_ledger(
    session: AsyncSession,
    user: User,
    monthly_income: Decimal,
    transactions: list[Transaction],
    start_date: date,
    end_date: date,
) -> None:
    account = BankAccount(
        user_id=user.id, account_number=f"DEMO-{user.id.hex[:10].upper()}", currency="LBP"
    )
    session.add(account)
    await session.flush()

    ledger_rows: list[BankLedger] = []
    month_cursor = date(start_date.year, start_date.month, 1)
    while month_cursor <= end_date:
        credit_date = max(month_cursor, start_date)
        ledger_rows.append(
            BankLedger(
                account_id=account.id,
                direction=LedgerDirection.CREDIT,
                amount=monthly_income,
                description="Monthly salary",
                occurred_at=datetime.combine(credit_date, time(9, 0), tzinfo=UTC),
            )
        )
        month_cursor = (month_cursor.replace(day=28) + timedelta(days=4)).replace(day=1)

    for tx in transactions:
        ledger_rows.append(
            BankLedger(
                account_id=account.id,
                direction=LedgerDirection.DEBIT,
                amount=tx.amount,
                description=f"{tx.category_code}: {tx.merchant_name}",
                transaction_id=tx.id,
                occurred_at=tx.occurred_at,
            )
        )

    session.add_all(ledger_rows)
    await session.commit()


async def _find_user_id(session: AsyncSession, email: str) -> uuid.UUID | None:
    result = await session.execute(select(User.id).where(User.email == email))
    return result.scalar_one_or_none()


async def _wipe_user_data(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Deletes every row for this user, in FK-safe order (several FKs here
    have no ON DELETE action, so children must go before their parents).
    """
    account_ids = (
        await session.execute(select(BankAccount.id).where(BankAccount.user_id == user_id))
    ).scalars().all()
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
    if account_ids:
        await session.execute(delete(BankLedger).where(BankLedger.account_id.in_(account_ids)))
    await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
    await session.execute(delete(ArousalState).where(ArousalState.user_id == user_id))
    await session.execute(delete(UserBaseline).where(UserBaseline.user_id == user_id))
    await session.execute(delete(Checkin).where(Checkin.user_id == user_id))
    await session.execute(delete(BankAccount).where(BankAccount.user_id == user_id))
    await session.execute(delete(UserGoal).where(UserGoal.user_id == user_id))
    await session.execute(delete(FinancialProfile).where(FinancialProfile.user_id == user_id))
    await session.execute(
        delete(QuestionnaireResponse).where(QuestionnaireResponse.user_id == user_id)
    )
    await session.execute(delete(UserSettings).where(UserSettings.user_id == user_id))
    await session.execute(delete(BiometricSample).where(BiometricSample.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()


async def _seed(session: AsyncSession, email: str, days: int) -> None:
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    user = _new_user(email, "Demo User")
    session.add(user)
    await session.flush()

    session.add(UserSettings(user_id=user.id))
    session.add(
        QuestionnaireResponse(
            user_id=user.id,
            completed_at=datetime.combine(start_date, time(10, 0), tzinfo=UTC),
            **_questionnaire_responses(),
        )
    )
    await session.commit()

    episodes = _generate_episodes(start_date, end_date)
    # Sorted ascending by construction (day-by-day, ascending time-of-day).
    samples = _generate_biometric_samples(user.id, start_date, end_date, episodes)
    checkin_specs = _generate_checkin_specs(start_date, end_date, episodes)

    # Interleaved with check-in scoring below rather than bulk-inserted up
    # front: refresh_baseline() must only ever see samples a wearable would
    # actually have streamed by a given check-in's entered_at, never samples
    # from later in the period. Handing it the full history up front would
    # mean every check-in — including the very first — sees a fully mature
    # baseline, silently skipping the real cold-start ('unknown' label)
    # path that live traffic goes through. See --cold-start for exercising
    # that path directly; even this interleaving won't reproduce it here,
    # since 10-minute sample cadence crosses the 30-sample source threshold
    # within hours, well before a realistic 2-4/week check-in catches it.
    sample_idx = 0
    checkin_results: list[tuple[Checkin, ArousalState]] = []
    for ts, category_code, valence in checkin_specs:
        due: list[BiometricSample] = []
        while sample_idx < len(samples) and samples[sample_idx].ts <= ts:
            due.append(samples[sample_idx])
            sample_idx += 1
        if due:
            session.add_all(due)
            await session.commit()

        heart_rate, hrv_ms, _spo2 = _physio_reading(ts, episodes)
        checkin = Checkin(
            user_id=user.id,
            category_code=category_code,
            valence=valence,
            heart_rate=heart_rate,
            hrv_ms=hrv_ms,
            entered_at=ts,
        )
        session.add(checkin)
        await session.commit()
        await session.refresh(checkin)

        # Exactly what POST /checkins does — see api/v1/checkins.py. No
        # arousal_state row is ever written by hand.
        await refresh_baseline(session, user.id)
        arousal = await score_checkin(session, checkin.id)
        checkin_results.append((checkin, arousal))

    # Whatever's left after the last check-in (including everything, if
    # there were no check-ins at all) — the biometric charts still need the
    # full period's data even though nothing scored against it.
    if sample_idx < len(samples):
        session.add_all(samples[sample_idx:])
        await session.commit()

    transactions: list[Transaction] = []
    for checkin, arousal in checkin_results:
        amount = _transaction_amount(checkin.category_code, arousal.label)
        transactions.append(
            Transaction(
                user_id=user.id,
                checkin_id=checkin.id,
                amount=amount,
                currency="LBP",
                category_code=checkin.category_code,
                merchant_name=random.choice(MERCHANTS[checkin.category_code]),
                occurred_at=checkin.entered_at + timedelta(minutes=random.uniform(2, 25)),
                was_planned=(
                    False if arousal.label == ArousalLabel.HIGH else random.random() < 0.8
                ),
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
                checkin_id=None,
                amount=_transaction_amount(category_code, None),
                currency="LBP",
                category_code=category_code,
                merchant_name=random.choice(MERCHANTS[category_code]),
                occurred_at=_random_waking_timestamp(start_date, end_date),
                was_planned=random.random() < 0.85,
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

    await _create_bank_account_and_ledger(
        session, user, monthly_income, transactions, start_date, end_date
    )

    await _print_summary(session, user, start_date, end_date)


async def _seed_cold_start(session: AsyncSession, email: str) -> None:
    """A brand-new user: a handful of check-ins, zero biometric_samples, no
    baseline history. Every check-in here should score 'unknown' — see the
    module docstring for why the default 60-day run never produces that.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=COLD_START_WINDOW_DAYS - 1)

    user = _new_user(email, "Cold Start Demo User")
    session.add(user)
    await session.flush()

    session.add(UserSettings(user_id=user.id))
    session.add(
        QuestionnaireResponse(
            user_id=user.id,
            completed_at=datetime.combine(start_date, time(10, 0), tzinfo=UTC),
            **_questionnaire_responses(),
        )
    )
    await session.commit()

    checkin_times = sorted(
        _random_waking_timestamp(start_date, end_date) for _ in range(COLD_START_CHECKINS)
    )

    checkin_results: list[tuple[Checkin, ArousalState]] = []
    for ts in checkin_times:
        # No episodes: this user has never had an elevated stretch, and the
        # point here is the cold-start label, not the stress pattern.
        heart_rate, hrv_ms, _spo2 = _physio_reading(ts, [])
        category_code = random.choices(CALM_CATEGORY_CHOICES, weights=CALM_CATEGORY_WEIGHTS)[0]
        valence = random.choices(CALM_VALENCE_CHOICES, weights=CALM_VALENCE_WEIGHTS)[0]
        checkin = Checkin(
            user_id=user.id,
            category_code=category_code,
            valence=valence,
            heart_rate=heart_rate,
            hrv_ms=hrv_ms,
            entered_at=ts,
        )
        session.add(checkin)
        await session.commit()
        await session.refresh(checkin)

        # Same real services as _seed() and POST /checkins — with zero
        # biometric_samples and fewer than 8 check-ins, baseline_factor
        # stays 0.0 the whole way through, so this should score 'unknown'
        # every time. See wellness.services.arousal._baseline_factor.
        await refresh_baseline(session, user.id)
        arousal = await score_checkin(session, checkin.id)
        checkin_results.append((checkin, arousal))

    transactions: list[Transaction] = []
    for checkin, arousal in checkin_results:
        transactions.append(
            Transaction(
                user_id=user.id,
                checkin_id=checkin.id,
                amount=_transaction_amount(checkin.category_code, arousal.label),
                currency="LBP",
                category_code=checkin.category_code,
                merchant_name=random.choice(MERCHANTS[checkin.category_code]),
                occurred_at=checkin.entered_at + timedelta(minutes=random.uniform(2, 25)),
                was_planned=random.random() < 0.8,
            )
        )
    session.add_all(transactions)
    await session.flush()

    daily_totals: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for tx in transactions:
        daily_totals[tx.occurred_at.date()] += tx.amount

    session.add(
        UserGoal(
            user_id=user.id,
            goal_type="monthly_budget",
            category_code=None,
            target_amount=_pick_monthly_budget(daily_totals),
            period="monthly",
            starts_on=start_date,
            is_active=True,
        )
    )

    total_spend = sum((tx.amount for tx in transactions), Decimal("0"))
    avg_monthly_spend = _money(float(total_spend) / (COLD_START_WINDOW_DAYS / 30))
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

    await _create_bank_account_and_ledger(
        session, user, monthly_income, transactions, start_date, end_date
    )

    print(f"\n=== Cold-start demo user seeded: {user.email} ({user.id}) ===")
    print(f"{len(checkin_results)} check-ins, {start_date} .. {end_date}, 0 biometric_samples.\n")
    print("Check-in arousal labels (all should be 'unknown'):")
    for checkin, arousal in checkin_results:
        print(f"  {checkin.entered_at}  category={checkin.category_code:<12} "
              f"label={arousal.label.value}")


async def _count(session: AsyncSession, stmt: Select[tuple[int]]) -> int:
    result = await session.execute(stmt)
    return result.scalar_one()


async def _print_summary(
    session: AsyncSession, user: User, start_date: date, end_date: date
) -> None:
    account_ids = (
        await session.execute(select(BankAccount.id).where(BankAccount.user_id == user.id))
    ).scalars().all()

    row_counts = {
        "user_settings": await _count(
            session, select(func.count()).select_from(UserSettings)
            .where(UserSettings.user_id == user.id)
        ),
        "financial_profile": await _count(
            session, select(func.count()).select_from(FinancialProfile)
            .where(FinancialProfile.user_id == user.id)
        ),
        "questionnaire_responses": await _count(
            session, select(func.count()).select_from(QuestionnaireResponse)
            .where(QuestionnaireResponse.user_id == user.id)
        ),
        "biometric_samples": await _count(
            session, select(func.count()).select_from(BiometricSample)
            .where(BiometricSample.user_id == user.id)
        ),
        "checkins": await _count(
            session, select(func.count()).select_from(Checkin).where(Checkin.user_id == user.id)
        ),
        "user_baseline": await _count(
            session, select(func.count()).select_from(UserBaseline)
            .where(UserBaseline.user_id == user.id)
        ),
        "arousal_state": await _count(
            session, select(func.count()).select_from(ArousalState)
            .where(ArousalState.user_id == user.id)
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
        "bank_ledger": (
            await _count(
                session, select(func.count()).select_from(BankLedger)
                .where(BankLedger.account_id.in_(account_ids))
            )
            if account_ids
            else 0
        ),
    }

    print(f"\n=== Demo data seeded for {user.email} ({user.id}) ===")
    print(f"Date range: {start_date} .. {end_date} ({(end_date - start_date).days + 1} days)\n")
    print("Row counts:")
    for table_name, count in row_counts.items():
        print(f"  {table_name:<24} {count}")

    analysis = await get_mood_spending_analysis(session, user.id, start_date, end_date, "month")
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


async def run(email: str, days: int, *, clean: bool, cold_start: bool) -> None:
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
        if cold_start:
            await _seed_cold_start(session, email)
        else:
            await _seed(session, email, days)
        break


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-email",
        default=None,
        help="Defaults to demo@example.com, or cold-start@example.com with --cold-start.",
    )
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument(
        "--clean", action="store_true", help="Remove the demo user and all their data, then exit."
    )
    parser.add_argument(
        "--cold-start",
        action="store_true",
        help=(
            f"Seed a separate, minimal user with {COLD_START_CHECKINS} check-ins and zero "
            "biometric_samples instead, so every check-in scores 'unknown' — the state the "
            "default run never produces. See the module docstring."
        ),
    )
    args = parser.parse_args()
    email = args.user_email or (COLD_START_EMAIL if args.cold_start else "demo@example.com")
    asyncio.run(run(email, args.days, clean=args.clean, cold_start=args.cold_start))


if __name__ == "__main__":
    main()

"""Insert synthetic data so mood_spend_correlation.py has something to correlate.

Not a real app seed script — just enough rows (one demo user, a batch of
checkins + arousal_state + linked transactions) to exercise the correlation
pipeline end-to-end. arousal_score is assigned directly (not derived from
the physiological readings) purely to make the demo correlation visible;
heart_rate is still populated because checkins requires at least one
reading. Safe to re-run: skips if the demo user already exists.

Usage:
    uv run python scripts/seed_test_data.py
"""

import asyncio
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from wellness.db import get_session
from wellness.models.arousal import ArousalState
from wellness.models.checkins import Checkin
from wellness.models.enums import ArousalLabel, ValenceLevel
from wellness.models.transactions import Transaction
from wellness.models.users import User

DEMO_EMAIL = "demo-correlation@example.com"
VALENCE_LEVELS = list(ValenceLevel)
CATEGORY_CODE = "mall"
N_ROWS = 150


def arousal_label_for(score: float) -> ArousalLabel:
    if score < 0.4:
        return ArousalLabel.CALM
    if score < 0.7:
        return ArousalLabel.ELEVATED
    return ArousalLabel.HIGH


async def main() -> None:
    session_gen = get_session()
    session = await anext(session_gen)
    try:
        existing = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing is not None:
            print(f"Demo user already exists ({existing.id}) — not re-seeding.")
            print(f"Try: uv run python scripts/mood_spend_correlation.py --user-id {existing.id}")
            return

        user = User(
            id=uuid.uuid4(),
            full_name="Demo Correlation User",
            email=DEMO_EMAIL,
            password_hash="not-a-real-hash",
            date_of_birth=date(1995, 1, 1),
        )
        session.add(user)
        await session.flush()

        base = datetime.now(tz=timezone.utc) - timedelta(days=N_ROWS)
        random.seed(42)

        for i in range(N_ROWS):
            # Engineered so arousal correlates with excess spend; valence is noise.
            arousal_score = random.uniform(0, 1)
            checkin = Checkin(
                user_id=user.id,
                category_code=CATEGORY_CODE,
                valence=random.choice(VALENCE_LEVELS),
                heart_rate=round(65 + arousal_score * 40 + random.gauss(0, 3), 1),
                entered_at=base + timedelta(hours=i),
            )
            session.add(checkin)
            await session.flush()

            session.add(
                ArousalState(
                    checkin_id=checkin.id,
                    user_id=user.id,
                    score=arousal_score,
                    label=arousal_label_for(arousal_score),
                    confidence=0.9,
                    metrics_used=1,
                    model_version="seed-test-v1",
                )
            )

            amount = max(5.0, 30 + 60 * arousal_score + random.gauss(0, 10))
            session.add(
                Transaction(
                    user_id=user.id,
                    checkin_id=checkin.id,
                    amount=Decimal(str(round(amount, 2))),
                    category_code=CATEGORY_CODE,
                    occurred_at=checkin.entered_at + timedelta(minutes=5),
                )
            )

        await session.commit()
        print(f"Seeded {N_ROWS} checkins/arousal_state/transactions for user {user.id} ({DEMO_EMAIL}).")
        print(f"Try: uv run python scripts/mood_spend_correlation.py --user-id {user.id}")
    finally:
        await session_gen.aclose()


if __name__ == "__main__":
    asyncio.run(main())

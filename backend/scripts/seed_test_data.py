"""Insert synthetic data so mood_spend_correlation.py has something to correlate.

Not a real app seed script — just enough rows (one demo user, a batch of
checkins + linked transactions) to exercise the correlation pipeline end-to-end.
The direct check-in arousal value is assigned to make the demo correlation
visible. Safe to re-run: skips if the demo user already exists.

Usage:
    uv run python scripts/seed_test_data.py
"""

import asyncio
import random
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from wellness.db import get_session
from wellness.models.banking import BankAccount
from wellness.models.checkins import Checkin
from wellness.models.enums import TransactionDirection, ValenceLevel
from wellness.models.transactions import Transaction
from wellness.models.users import User

DEMO_EMAIL = "demo-correlation@example.com"
VALENCE_LEVELS = list(ValenceLevel)
CATEGORY_CODE = "mall"
N_ROWS = 150


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

        account = BankAccount(
            user_id=user.id,
            account_number=f"DEMO-{user.id.hex[:12].upper()}",
            currency="LBP",
        )
        session.add(account)
        await session.flush()

        base = datetime.now(tz=UTC) - timedelta(days=N_ROWS)
        random.seed(42)

        for i in range(N_ROWS):
            # Engineered so arousal correlates with excess spend; valence is noise.
            arousal_z = random.uniform(-2, 2)
            checkin = Checkin(
                user_id=user.id,
                category_code=CATEGORY_CODE,
                valence=random.choice(VALENCE_LEVELS),
                arousal_input_mode="manual",
                arousal_z=arousal_z,
                entered_at=base + timedelta(hours=i),
            )
            session.add(checkin)
            await session.flush()

            amount = max(5.0, 30 + 15 * (arousal_z + 2) + random.gauss(0, 10))
            session.add(
                Transaction(
                    user_id=user.id,
                    account_id=account.id,
                    checkin_id=checkin.id,
                    direction=TransactionDirection.DEBIT,
                    amount=Decimal(str(round(amount, 2))),
                    category_code=CATEGORY_CODE,
                    occurred_at=checkin.entered_at + timedelta(minutes=5),
                )
            )

        await session.commit()
        print(
            f"Seeded {N_ROWS} checkins/transactions "
            f"for user {user.id} ({DEMO_EMAIL})."
        )
        print(f"Try: uv run python scripts/mood_spend_correlation.py --user-id {user.id}")
    finally:
        await session_gen.aclose()


if __name__ == "__main__":
    asyncio.run(main())

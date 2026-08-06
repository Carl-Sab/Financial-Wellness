# Financial Wellness

> Feel what your spending does to you — before it happens.

A spending insight app built around a simple loop: before a purchase, the
user logs a quick physiological check-in (heart rate, HRV, EDA, SpO2, skin
temp — whatever their wearable/device gives them) and how they're feeling
(valence). That gets scored into an arousal reading relative to the user's
own baseline, and — when elevated arousal or excess spending shows a real
pattern — the app can nudge them before an impulse becomes a transaction.

## How it's put together

Backend: **FastAPI** + **SQLAlchemy (async)** + **PostgreSQL**, managed with
`uv`. Full schema in [`backend/schema.sql`](backend/schema.sql).

The data model is split into two domains, kept deliberately separate:

- **Arousal-scoring** (`models/checkins.py`, `models/baseline.py`,
  `models/arousal.py`) — a manual physiological check-in (`Checkin`: heart
  rate, HRV, EDA, SpO2, skin temp, EEG — all nullable, plus a `valence`
  rating), the user's own rolling per-metric baseline (`UserBaseline`), and
  the derived arousal score/label computed from the two (`ArousalState`).
  Scored on physiology alone, relative to the user's own baseline —
  spending data plays no role in that computation.
- **Spending** (`models/transactions.py`, `models/financial.py`,
  `models/banking.py`, `models/goals.py`, `models/categories.py`) —
  transactions (optionally linked back to the checkin that preceded them via
  `checkin_id`), versioned financial profile snapshots, bank
  accounts/ledgers, user-defined spending goals, and the shared spending
  category lookup table.

**The architectural boundary is enforced by convention, not just code
organization**: nothing in the spending-domain modules may import from or be
imported by the arousal-scoring modules — arousal is analysed *against*
spending, never used to *produce* it. See the boundary comment at the top of
`models/transactions.py` and each module for the full rationale.

Also: `models/notifications.py` (nudge outbox + delivery feedback,
downstream of both domains via plain FK columns, no ORM relationship import)
and `models/users.py` (accounts + the one-time signup questionnaire scoring
impulse tendency, self-control, hedonic/utilitarian shopping traits).

The frontend is currently a single standalone landing/marketing page,
[`FinancialWellnessLanding.jsx`](FinancialWellnessLanding.jsx), at the repo
root — not yet wired into a build.

## Mood/arousal vs. spending analysis

[`backend/scripts/mood_spend_correlation.py`](backend/scripts/mood_spend_correlation.py)
answers: does how someone feels at the moment of a purchase relate to how
much *more* than usual they spend?

- Only looks at transactions with a linked checkin (`transactions.checkin_id`)
  — that's what carries the mood data.
- **Happiness** / **sadness**: `checkins.valence` mapped to a numeric
  −2..+2 scale, sadness being the sign-flipped read of the same scale (so
  their correlations with spend are mirror images of each other by
  construction — not two independent findings).
- **Arousal**: `arousal_state.score` (0-1), joined via the same checkin.
- **Excess spend**: `transaction.amount` minus that user's own average
  transaction amount in the same category — the same "relative to your own
  baseline" logic the app already uses for arousal itself, applied to spend.

It produces two plots (a scatter+trendline per axis, and a bar chart ranking
correlation strength) and, unless `--skip-ai-report` is passed, feeds the
exact correlation numbers plus those plot images to Claude (via the same
Pydantic AI Gateway key used in the game-store project) to get back a
written report — [`ai_report.py`](backend/scripts/ai_report.py) has the
prompt.

```
uv run python scripts/mood_spend_correlation.py [--user-id UUID] [--skip-ai-report]
```

Plots and the AI report land in `scripts/output/`.

## Current status

- ✅ Full SQLAlchemy schema matching `schema.sql`, with an explicit
  constraint naming convention (`models/base.py`)
- ✅ Async DB session factory (`db.py`) + pydantic-settings config
  (`config.py`)
- ✅ `docker-compose.yml` for Postgres
- ✅ `scripts/mood_spend_correlation.py` + `scripts/ai_report.py` — mood vs.
  excess-spend correlation, plots, and an AI-written report
- ⬜ No FastAPI routes or app entrypoint yet
- ⬜ No Alembic migrations generated yet (schema is applied via `schema.sql`
  directly for now)
- ⬜ No tests yet (tooling is already in place: pytest, pytest-asyncio,
  testcontainers)

## Getting started

1. Start Postgres:
   ```
   cd backend
   docker compose up -d
   ```
   `init.sql` only enables the `pgcrypto` extension — the actual tables
   aren't created automatically yet, so apply the schema once:
   ```
   docker compose exec -T db psql -U wellness -d wellness < schema.sql
   ```
2. Copy the env file and adjust if needed:
   ```
   cp .env.example .env
   ```
   `API_KEY_SECRET_FROM_EURISKO` is only needed for the AI report step of
   the correlation script — everything else works without it.
3. Install dependencies:
   ```
   uv sync
   ```
4. Run the mood/spend correlation analysis:
   ```
   uv run python scripts/mood_spend_correlation.py
   ```

## Project structure

```
backend/
  src/wellness/
    config.py            # pydantic-settings
    db.py                 # async SQLAlchemy engine/session factory
    logging.py
    models/
      base.py             # declarative Base + naming convention
      enums.py            # ValenceLevel, ArousalLabel, Level3, ...
      users.py            # User, QuestionnaireResponse
      checkins.py         # Checkin (manual physiological + valence reading)
      baseline.py          # UserBaseline (per-user, per-metric mean/sd)
      arousal.py           # ArousalState (derived from checkin vs. baseline)
      categories.py        # Category (shared spending category lookup)
      transactions.py      # Transaction (optionally linked to a checkin)
      financial.py          # FinancialProfile (versioned, never updated in place)
      banking.py            # BankAccount, BankLedger
      goals.py               # UserGoal
      notifications.py       # UserSettings, NotificationOutbox, NotificationFeedback
  scripts/
    mood_spend_correlation.py  # mood/arousal vs. excess-spend correlation + plots
    ai_report.py                 # AI write-up of the correlation results
  schema.sql                # source of truth for the Postgres schema
  docker-compose.yml       # Postgres
  init.sql
  .env.example
FinancialWellnessLanding.jsx  # marketing/landing page (React)
```

## Dev tooling

Configured in `pyproject.toml`: `ruff` (lint + import sort), `mypy --strict`
(with the SQLAlchemy plugin), `pytest` + `pytest-asyncio` (async test mode
on by default), and `testcontainers[postgres]` for integration tests against
a real Postgres.

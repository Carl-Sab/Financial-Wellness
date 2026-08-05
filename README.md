# Financial Wellness

> Feel what your spending does to you — before it happens.

A wearable-linked spending insight app. It reads physiological signals from a
wearable device (heart rate, HRV, EDA/skin conductance, respiration, skin
temperature), scores arousal/stress against each user's own rolling baseline,
and — when elevated arousal lines up with financial context — sends a gentle
nudge notification before an impulse becomes a transaction.

## How it's put together

Backend: **FastAPI** + **SQLAlchemy (async)** + **TimescaleDB** (Postgres with
the time-series extension) + **Redis**, managed with `uv`.

The data model is split into four domains, kept deliberately separate:

- **Biometrics & arousal** (`models/biometrics.py`) — raw biometric samples
  (`BiometricSample`), per-user rolling baselines (`UserBaseline`), and
  arousal scoring results (`ArousalState`). Arousal is scored on physiology
  alone, relative to the user's own baseline — financial data plays no role
  in that computation.
- **Financial** (`models/financial.py`) — versioned financial profile
  snapshots (`FinancialProfile`: income, spend, fixed costs). Used only for
  user-facing reporting.
- **Notifications** (`models/notifications.py`) — an outbox of nudges
  (`NotificationOutbox`, with trigger reasoning and a snapshot arousal score)
  plus a feedback log (`NotificationFeedback`: delivered / opened / dismissed
  / marked helpful).
- **Users** (`models/users.py`) — accounts (`User`), demographic profile
  (`UserProfile`), and an append-only per-feature consent log (`UserConsent`)
  — biometric collection and notifications can be granted or revoked
  independently.

**The architectural boundary is enforced by convention, not just code
organization**: nothing in `models/financial.py` may import from or be
imported by `models/biometrics.py`, so any accidental coupling between
"how stressed you are" and "how much you make" shows up immediately as an
out-of-place import. See the boundary comment at the top of each module.

The frontend is currently a single standalone landing/marketing page,
[`FinancialWellnessLanding.jsx`](FinancialWellnessLanding.jsx), at the repo
root — not yet wired into a build.

## Current status

This is an early scaffold, not a running app yet.

- ✅ SQLAlchemy models for all four domains, with an explicit constraint
  naming convention (`models/base.py`) so future Alembic migrations get
  stable, predictable names
- ✅ Async DB session factory (`db.py`) + pydantic-settings config
  (`config.py`)
- ✅ `docker-compose.yml` for TimescaleDB + Redis
- ✅ `scripts/mood_spend_correlation.py` — standalone analysis: joins spend
  transactions to the most recent preceding mood reading (joyful/stressed/sad,
  each 0-100) and reports/plots the Pearson correlation between spend amount
  and each mood score. Deliberately schema-agnostic (reads CSVs or raw SQL
  queries, not ORM models) since the actual mood/transaction tables are being
  designed by a teammate; overspend classification itself is a separate model
  someone else owns.
- ⬜ No FastAPI routes or app entrypoint yet
- ⬜ No Alembic migrations generated yet
- ⬜ No tests yet (tooling is already in place: pytest, pytest-asyncio,
  testcontainers)

## Getting started

1. Start Postgres/TimescaleDB + Redis:
   ```
   cd backend
   docker compose up -d
   ```
2. Copy the env file and adjust if needed:
   ```
   cp .env.example .env
   ```
3. Install dependencies:
   ```
   uv sync
   ```
4. Run the mood/spend correlation analysis, pointing it at either CSVs or
   SQL queries for the transaction and mood data (see the script's docstring
   for the required columns):
   ```
   uv run python scripts/mood_spend_correlation.py \
     --transactions-csv transactions.csv --moods-csv moods.csv
   ```
   Plots land in `scripts/output/`.

## Project structure

```
backend/
  src/wellness/
    config.py            # pydantic-settings
    db.py                 # async SQLAlchemy engine/session factory
    logging.py
    models/
      base.py             # declarative Base + naming convention
      enums.py
      biometrics.py       # BiometricSample, ArousalState, UserBaseline
      financial.py        # FinancialProfile (versioned, never updated in place)
      notifications.py    # NotificationOutbox, NotificationFeedback
      users.py            # User, UserConsent, UserProfile
  scripts/
    mood_spend_correlation.py  # mood vs. spend correlation + plots (CSV/SQL input, no ORM dependency)
  docker-compose.yml       # TimescaleDB + Redis
  init.sql                 # enables the timescaledb extension
  .env.example
FinancialWellnessLanding.jsx  # marketing/landing page (React)
```

## Dev tooling

Configured in `pyproject.toml`: `ruff` (lint + import sort), `mypy --strict`
(with the SQLAlchemy plugin), `pytest` + `pytest-asyncio` (async test mode
on by default), and `testcontainers[postgres]` for integration tests against
a real Postgres.

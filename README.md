# Financial Wellness

> Feel what your spending does to you before it happens.

A spending insight app built around a simple loop: before a purchase, the
user logs a quick physiological check-in (heart rate, HRV, EDA, SpO2, skin
temp — whatever their wearable/device gives them) and how they're feeling
(valence). That gets scored into an arousal reading relative to the user's
own baseline, and — when elevated arousal or excess spending shows a real
pattern — the app can nudge them before an impulse becomes a transaction.

## Running the app

Everything below happens in `backend/` unless noted. You need Docker and
[`uv`](https://docs.astral.sh/uv/) installed.

**1. One-time setup:**
```
cd backend
docker compose up -d              # starts Postgres
uv sync                           # installs dependencies
cp .env.example .env              # copy env file (defaults already match docker-compose)
uv run alembic upgrade head       # creates all the tables
uv run python scripts/seed_test_data.py   # optional: fake data so there's something to see
```
The seed script prints a user ID at the end (e.g.
`6bb71316-7dc5-486d-bcfa-882bb814f8e5`) — copy it, you'll need it in step 3.
`API_KEY_SECRET_FROM_EURISKO` in `.env` is only needed if you want the AI
report (see below) — everything else works without it.

**2. Start the API** (leave this running in its own terminal):
```
uv run uvicorn wellness.main:app --reload --port 8000
```
Confirm it's up at `http://localhost:8000/docs`.

**3. Start the frontend** (a *second* terminal):
```
cd frontend
python -m http.server 5500
```
Open `http://localhost:5500` in your browser. Paste the user ID from step 1
into the "User ID" box (or leave it blank to include every user), optionally
check "Include AI report," and click **Run Analysis**. You should see a
correlation table and two plots appear.

That's the whole app right now — a correlation viewer. There's no
login/register UI yet (see "Current status" below for what's not built).

## How it's put together

Backend: **FastAPI** + **SQLAlchemy (async)** + **PostgreSQL** + **Alembic**,
managed with `uv`. `backend/schema.sql` is a human-readable reference copy of
the schema — **Alembic migrations (`backend/alembic/versions/`) are the real
source of truth**; always set the DB up via `alembic upgrade head`, not by
applying `schema.sql` directly, or you'll drift out of sync with the models.

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

## API

`backend/src/wellness/api/v1/` has CRUD routers for every table (users,
checkins, transactions, arousal-state (read-only), goals, bank accounts/
ledger, categories, user baseline, questionnaire responses) plus one
analysis endpoint. **All of it is smoke-test only — no auth** (see the
warning comment at the top of each router file); don't expose this beyond
local dev as-is. Run command is in "Running the app" above; interactive
docs at `http://localhost:8000/docs` once it's up.

### Mood/arousal vs. excess-spend correlation

`GET /api/v1/analysis/mood-spend-correlation?user_id=<uuid>&include_ai_report=true`

Answers: does how someone feels at the moment of a purchase relate to how
much *more* than usual they spend? The core logic lives in
[`wellness/analysis/mood_spend.py`](backend/src/wellness/analysis/mood_spend.py)
and is shared between this endpoint and the CLI script below, so they can't
drift apart.

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

Returns the correlation table, the two plots as base64 PNGs, and — if
`include_ai_report=true` and `API_KEY_SECRET_FROM_EURISKO` is set — a
written report from Claude (via the same Pydantic AI Gateway key used in the
game-store project;
[`wellness/analysis/report.py`](backend/src/wellness/analysis/report.py)
has the prompt).

There's also a CLI version for terminal use:
```
uv run python scripts/mood_spend_correlation.py [--user-id UUID] [--skip-ai-report]
```
Plots and the AI report land in `scripts/output/`.

## Frontend

[`frontend/`](frontend/) is a plain HTML/CSS/JS page (no build step) that
calls the correlation endpoint above and renders the results: a table, the
two plots, and the AI report (if requested) as rendered markdown. Run
command is in "Running the app" above. It expects the API on
`http://localhost:8000` — change `API_BASE_URL` in `frontend/js/app.js` if
you're running it on a different port.

There's also a separate standalone landing/marketing page,
[`FinancialWellnessLanding.jsx`](FinancialWellnessLanding.jsx), at the repo
root — not wired into `frontend/`.

## Current status

- ✅ Full SQLAlchemy schema + matching Alembic migrations
  (`alembic/versions/0001`, `0002`)
- ✅ FastAPI app (`wellness/main.py`) with CRUD routers for every table —
  **smoke-test only, no auth yet**
- ✅ `GET /api/v1/analysis/mood-spend-correlation` + a plain HTML/JS frontend
  for it (`frontend/`)
- ✅ `scripts/mood_spend_correlation.py` — CLI version of the same analysis
- ⬜ No real authentication/authorization
- ⬜ No arousal-scoring service yet (creating a checkin does *not* trigger
  baseline recomputation or arousal scoring — that's still manual/TODO)
- ✅ Tests exist for several routers (`backend/tests/`) — `uv run pytest`

## Project structure

```
backend/
  src/wellness/
    main.py               # FastAPI app entrypoint
    config.py              # pydantic-settings
    db.py                  # async SQLAlchemy engine/session factory
    security.py             # password hashing (smoke-test grade, see TODO in file)
    logging.py
    api/
      deps.py               # pagination, etc.
      errors.py             # commit_or_409, not_found
      v1/                   # one router per table + analysis.py
    schemas/                # Pydantic request/response models, one file per table
    analysis/
      mood_spend.py          # mood/arousal vs. excess-spend correlation (shared core)
      report.py               # AI write-up of the correlation results
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
  alembic/versions/       # source of truth for the DB schema
  scripts/
    mood_spend_correlation.py  # CLI: mood/arousal vs. excess-spend correlation + plots
    seed_test_data.py           # synthetic demo data for the above
  tests/
  schema.sql                # human-readable reference copy — NOT applied directly, see above
  docker-compose.yml       # Postgres
  init.sql
  .env.example
frontend/
  index.html               # correlation results viewer
  js/app.js
  css/style.css
FinancialWellnessLanding.jsx  # marketing/landing page (React), unrelated to frontend/
```

## Dev tooling

Configured in `pyproject.toml`: `ruff` (lint + import sort), `mypy --strict`
(with the SQLAlchemy plugin), `pytest` + `pytest-asyncio` (async test mode
on by default), and `testcontainers[postgres]` for integration tests against
a real Postgres.

# Financial Wellness

> Feel what your spending does to you before it happens.

A spending insight app built around a simple loop: before a purchase, the
user logs a quick physiological check-in (heart rate, HRV, EDA, SpO2, skin
temp — whatever their wearable/device gives them) and how they're feeling
(valence). That gets scored into an arousal reading relative to the user's
own baseline, and — when elevated arousal or excess spending shows a real
pattern — the app can nudge them before an impulse becomes a transaction.

## Running the app

You need Docker, [`uv`](https://docs.astral.sh/uv/), and Node installed.
There are two parts: the API (`backend/`) and the actual app (`web/`) — a
React site with a landing page, sign up, and log in, all working end to end.

### One-time setup

```
cd backend
docker compose up -d              # starts Postgres
uv sync                           # installs backend dependencies
cp .env.example .env
```
Then open `backend/.env` and set `JWT_SECRET` — the app **will not start**
without it (no placeholder default is shipped, on purpose: see the comment
in `.env.example`). Generate one and paste it in:
```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
`API_KEY_SECRET_FROM_EURISKO` in `.env` is only needed for the AI report
feature (see below) — everything else works without it.

```
uv run alembic upgrade head       # creates all the tables
cd ../web
npm install                       # installs frontend dependencies
```

### Every time after that

Three terminals, all left running:

**1. Database** (`backend/`, if it's not already up):
```
docker compose up -d
```

**2. API** (`backend/`):
```
uv run uvicorn wellness.main:app --reload --port 8000
```
Confirm it's up at `http://localhost:8000/docs`.

**3. The app** (`web/`):
```
npm run dev
```
Open `http://localhost:5173`. `web/vite.config.js` proxies `/api/*` to the
backend automatically, so nothing else to configure. Register an account, or
log in if you already have one — that's real now, not a placeholder.

Optional — seed a full realistic demo user (biometric samples, check-ins
scored through the real arousal pipeline, transactions, a budget, a bank
ledger) so there's something to look at beyond your own account:
```
cd backend
uv run python scripts/seed_demo_data.py
```

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
analysis endpoint. **All of that is still smoke-test only — no auth applied**
(see the warning comment at the top of each router file); don't expose it
beyond local dev as-is.

The one router that *is* real: `auth.py` —
`POST /api/v1/auth/{register,login,refresh,logout}` and `GET /api/v1/auth/me`.
Access tokens are short-lived JWTs; refresh tokens are opaque, stored
hashed, delivered as an httpOnly cookie, and rotated on every use (reuse of
an already-used one revokes the whole session family — see
`wellness/models/auth.py`). A `get_current_user` dependency exists for
gating other routes the same way, just isn't used anywhere yet.

Run command is in "Running the app" above; interactive docs at
`http://localhost:8000/docs` once it's up.

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

**[`web/`](web/)** is the real app — a Vite + React site: landing page, a
two-step sign up, log in, and a working JWT session (in-memory access
token, httpOnly-cookie refresh token that survives a page reload). Run
command is in "Running the app" above.

`frontend/` is a separate, older tool — a plain HTML/JS page (no build
step, no relation to `web/`) that calls the mood/spend correlation endpoint
below and renders a table, two plots, and an AI report as markdown:
```
cd frontend
python -m http.server 5500
```
Open `http://localhost:5500`. It needs a user ID — `uv run python
scripts/seed_test_data.py` (in `backend/`, a narrower/older seed than
`seed_demo_data.py` above) prints one you can paste in. Expects the API on
`http://localhost:8000` — change `API_BASE_URL` in `frontend/js/app.js` if
you're running it elsewhere.

## Current status

- ✅ Full SQLAlchemy schema + matching Alembic migrations
  (`alembic/versions/0001`–`0006`)
- ✅ FastAPI app (`wellness/main.py`) with CRUD routers for every table —
  still smoke-test only / no auth applied to them (see the warning comment
  at the top of each router file)
- ✅ Real JWT authentication: register, login, refresh-token rotation with
  reuse detection, logout, rate-limited login, `GET /auth/me` — see
  `wellness/api/v1/auth.py`. A `get_current_user` dependency exists
  (`wellness/api/deps.py`) but isn't applied to any router yet.
- ✅ `web/` — the real frontend: landing page, working sign up / log in
  against the auth endpoints above
- ✅ `GET /api/v1/analysis/mood-spend-correlation` + the older plain HTML/JS
  viewer for it (`frontend/`)
- ✅ `scripts/mood_spend_correlation.py` — CLI version of the same analysis
- ✅ Arousal-scoring is live: creating a checkin (`POST /api/v1/checkins`)
  triggers baseline recomputation and arousal scoring for real, no manual
  step needed
- ⬜ No protected routes yet — nothing in the app actually requires being
  logged in (the pieces exist, just not wired to anything)
- ✅ Tests exist for every router plus the full auth flow
  (`backend/tests/`) — `uv run pytest`

## Project structure

```
backend/
  src/wellness/
    main.py               # FastAPI app entrypoint, CORS (scoped to FRONTEND_ORIGIN)
    config.py              # pydantic-settings — JWT_SECRET etc.
    db.py                  # async SQLAlchemy engine/session factory
    security.py             # password hashing + JWT access-token encode/decode
    logging.py
    api/
      deps.py               # pagination, get_current_user (unapplied so far)
      errors.py             # commit_or_409, not_found
      v1/                   # one router per table + analysis.py + auth.py
    schemas/                # Pydantic request/response models, one file per table
    analysis/
      mood_spend.py          # mood/arousal vs. excess-spend correlation (shared core)
      report.py               # AI write-up of the correlation results
    models/
      base.py             # declarative Base + naming convention
      enums.py            # ValenceLevel, ArousalLabel, Level3, ...
      users.py            # User, QuestionnaireResponse
      auth.py             # RefreshToken, LoginFailure (session + rate-limit storage)
      checkins.py         # Checkin (manual physiological + valence reading)
      baseline.py          # UserBaseline (per-user, per-metric mean/sd)
      arousal.py           # ArousalState (derived from checkin vs. baseline)
      biometric_samples.py  # wearable-sourced readings, feeds baseline/arousal
      categories.py        # Category (shared spending category lookup)
      transactions.py      # Transaction (optionally linked to a checkin)
      financial.py          # FinancialProfile (versioned, never updated in place)
      banking.py            # BankAccount, BankLedger
      goals.py               # UserGoal
      notifications.py       # UserSettings, NotificationOutbox, NotificationFeedback
  alembic/versions/       # source of truth for the DB schema (0001–0006)
  scripts/
    mood_spend_correlation.py  # CLI: mood/arousal vs. excess-spend correlation + plots
    seed_demo_data.py           # full realistic demo user — the one to use day to day
    seed_biometric_samples.py   # just wearable sample data, for one existing user
    seed_test_data.py           # narrower/older seed, for the frontend/ correlation viewer
  tests/
  schema.sql                # human-readable reference copy — NOT applied directly, see above
  docker-compose.yml       # Postgres
  init.sql
  .env.example
web/                        # the real frontend — Vite + React
  src/
    pages/                   # LandingPage, Signup, Login, one file per route
    components/landing/      # Header, Hero, Features, HowItWorks, JoinBand, Footer
    context/AuthContext.jsx  # access token in memory, refresh-on-mount, login/logout/register
    lib/api.js                # fetch wrapper: attaches the token, retries once on 401
  vite.config.js            # proxies /api/* to the backend — no CORS setup needed in dev
frontend/                   # older, separate — plain HTML/JS correlation viewer
  index.html
  js/app.js
  css/style.css
```

## Dev tooling

Configured in `pyproject.toml`: `ruff` (lint + import sort), `mypy --strict`
(with the SQLAlchemy plugin), `pytest` + `pytest-asyncio` (async test mode
on by default), and `testcontainers[postgres]` for integration tests against
a real Postgres.

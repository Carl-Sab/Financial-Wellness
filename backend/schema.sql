-- =====================================================================
-- Wellness & spending app - database schema (v3)
-- Plain PostgreSQL 16.
--
-- Data model: the user records subjective arousal metrics in a check-in
-- immediately before a transaction. Per-user normalization statistics are
-- stored separately and populated explicitly; check-ins do not update them.
--
-- Boundary: financial data is never read by the arousal scoring path.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- for gen_random_uuid()


-- =====================================================================
-- 1. USERS
-- =====================================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    date_of_birth   DATE NOT NULL,
    phone           TEXT,
    address         TEXT,
    city            TEXT,
    country         TEXT,
    timezone        TEXT NOT NULL DEFAULT 'Asia/Beirut',
    currency        TEXT NOT NULL DEFAULT 'LBP',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Age is derived, never stored - it would go stale.
--   SELECT date_part('year', age(date_of_birth)) FROM users;


-- =====================================================================
-- 2. SIGNUP QUESTIONNAIRE
--
-- Four scales, all trait-framed, all administered once at signup.
-- Raw item responses are kept alongside the computed scores so the
-- scores can be recomputed or checked for reliability later.
-- =====================================================================

CREATE TABLE questionnaire_responses (
    id                      BIGSERIAL PRIMARY KEY,
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Rook & Fisher (1995), 9 items, 1-5
    impulse_tendency_score  REAL CHECK (impulse_tendency_score BETWEEN 1 AND 5),

    -- Tangney et al. (2004), 13 items, 1-5
    self_control_score      REAL CHECK (self_control_score BETWEEN 1 AND 5),

    -- Babin et al. (1994) adapted to trait framing, 11 items, 1-7
    hedonic_score           REAL CHECK (hedonic_score BETWEEN 1 AND 7),

    -- Babin et al. (1994) adapted to trait framing, 4 items, 1-7
    utilitarian_score       REAL CHECK (utilitarian_score BETWEEN 1 AND 7),

    raw_responses           JSONB NOT NULL,  -- {"ibt_1":4,"sc_1":2,"hed_1":6,...}
    instrument_version      TEXT NOT NULL DEFAULT 'v1',
    completed_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON questionnaire_responses (user_id, completed_at DESC);


-- =====================================================================
-- 3. CATEGORIES
-- =====================================================================

CREATE TYPE level_3 AS ENUM ('low', 'mid', 'high');

CREATE TABLE categories (
    code                TEXT PRIMARY KEY,
    label               TEXT NOT NULL,
    identity_level      level_3 NOT NULL,
    price_level         level_3 NOT NULL,
    advertising_level   level_3 NOT NULL,
    distribution_level  level_3 NOT NULL,
    stimuli_score       REAL,    -- legacy derived value; see section 8
    marketing_score     REAL NOT NULL CHECK (marketing_score BETWEEN 0 AND 1)
);


-- =====================================================================
-- 4. CHECK-IN  (the core table)
--
-- One row per pre-transaction check-in. New clients use either manual
-- arousal (one direct value) or detailed arousal (five separate values).
-- The raw physiological columns remain for legacy clients/history.
--
-- NOTE ON EEG: consumer wearables do not report EEG. The column exists
-- because it was requested, but expect it to be null in practice.
-- =====================================================================

CREATE TYPE valence_level AS ENUM (
    'very_unpleasant', 'unpleasant', 'neutral', 'pleasant', 'very_pleasant'
);

CREATE TABLE checkins (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_code       TEXT NOT NULL REFERENCES categories(code),
    valence             valence_level NOT NULL,

    -- subjective questionnaire inputs: every value is -2, -1, 0, 1, or 2
    arousal_input_mode  TEXT CHECK (arousal_input_mode IN ('manual', 'detailed')),
    arousal_z           REAL CHECK (arousal_z IN (-2, -1, 0, 1, 2)),
    perceived_heart_rate REAL CHECK (perceived_heart_rate IN (-2, -1, 0, 1, 2)),
    perceived_heartbeat_steadiness REAL
        CHECK (perceived_heartbeat_steadiness IN (-2, -1, 0, 1, 2)),
    perceived_sweating  REAL CHECK (perceived_sweating IN (-2, -1, 0, 1, 2)),
    perceived_respiration REAL CHECK (perceived_respiration IN (-2, -1, 0, 1, 2)),
    perceived_temperature_difference REAL
        CHECK (perceived_temperature_difference IN (-2, -1, 0, 1, 2)),

    entered_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT arousal_input_contract CHECK (
        (arousal_input_mode IS NULL AND arousal_z IS NULL
            AND perceived_heart_rate IS NULL
            AND perceived_heartbeat_steadiness IS NULL
            AND perceived_sweating IS NULL AND perceived_respiration IS NULL
            AND perceived_temperature_difference IS NULL)
        OR (arousal_input_mode = 'manual'
            AND arousal_z IS NOT NULL
            AND perceived_heart_rate IS NULL
            AND perceived_heartbeat_steadiness IS NULL
            AND perceived_sweating IS NULL AND perceived_respiration IS NULL
            AND perceived_temperature_difference IS NULL)
        OR (arousal_input_mode = 'detailed'
            AND arousal_z IS NULL
            AND perceived_heart_rate IS NOT NULL
            AND perceived_heartbeat_steadiness IS NOT NULL
            AND perceived_sweating IS NOT NULL AND perceived_respiration IS NOT NULL
            AND perceived_temperature_difference IS NOT NULL)
    )
);
CREATE INDEX ON checkins (user_id, entered_at DESC);


-- =====================================================================
-- 5. PER-USER METRIC NORMALIZATION STATISTICS
--
-- Storage only. Values are inserted or replaced explicitly; creating,
-- updating, or deleting a check-in does not change this table.
-- =====================================================================

CREATE TABLE user_metric_statistics (
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    metric        TEXT NOT NULL CHECK (metric IN (
        'perceived_heart_rate',
        'perceived_heartbeat_steadiness',
        'perceived_sweating',
        'perceived_respiration',
        'perceived_temperature_difference'
    )),
    mean_value    REAL NOT NULL,
    std_value     REAL NOT NULL CHECK (std_value >= 0),
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (user_id, metric)
);


-- =====================================================================
-- 7. BANK ACCOUNTS AND UNIFIED TRANSACTIONS
--
-- Both account balances and purchase history are derived from transactions.
-- There is no separate bank_ledger table or mutable current-balance column.
-- =====================================================================

CREATE TYPE transaction_direction AS ENUM ('credit', 'debit');

CREATE TABLE bank_accounts (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_number      TEXT NOT NULL UNIQUE,
    currency            TEXT NOT NULL DEFAULT 'LBP',
    opening_balance     NUMERIC(14,2) NOT NULL DEFAULT 0,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    opened_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE transactions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id      BIGINT NOT NULL REFERENCES bank_accounts(id),
    checkin_id      BIGINT REFERENCES checkins(id),  -- the check-in that preceded it
    direction       transaction_direction NOT NULL DEFAULT 'debit',
    amount          NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    currency        TEXT NOT NULL DEFAULT 'LBP',
    category_code   TEXT REFERENCES categories(code),
    description     TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON transactions (user_id, occurred_at DESC);
CREATE INDEX ON transactions (account_id, occurred_at DESC);
CREATE INDEX ON transactions (user_id, category_code, occurred_at DESC);


CREATE TABLE financial_profile (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    monthly_income      NUMERIC(14,2),
    avg_monthly_spend   NUMERIC(14,2),
    currency            TEXT NOT NULL DEFAULT 'LBP',
    valid_from          TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to            TIMESTAMPTZ
);
CREATE UNIQUE INDEX one_current_financial_profile
    ON financial_profile (user_id) WHERE valid_to IS NULL;


-- =====================================================================
-- 8. NOTIFICATIONS
-- =====================================================================

CREATE TYPE outbox_status AS ENUM ('pending', 'sent', 'failed', 'suppressed');

CREATE TABLE notification_outbox (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    checkin_id          BIGINT REFERENCES checkins(id),
    body                TEXT,
    trigger_reason      TEXT NOT NULL,
    arousal_score       REAL,
    status              outbox_status NOT NULL DEFAULT 'pending',
    suppression_reason  TEXT,
    used_fallback       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at             TIMESTAMPTZ
);
CREATE INDEX ON notification_outbox (user_id, created_at DESC);

CREATE TYPE feedback_event AS ENUM (
    'delivered', 'opened', 'dismissed', 'marked_helpful', 'marked_not_now'
);

CREATE TABLE notification_feedback (
    id          BIGSERIAL PRIMARY KEY,
    outbox_id   BIGINT NOT NULL REFERENCES notification_outbox(id) ON DELETE CASCADE,
    event       feedback_event NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


--
-- Repeat with hrv_ms, eda_microsiemens, spo2_percent, skin_temp_c.

-- Then the z-score for the new reading:
--   z = (reading - mean_value) / NULLIF(sd_value, 0)
--
-- Guard rails:
--   sample_n < 8   -> sd is unstable; store arousal label 'unknown'
--   sd_value = 0   -> all readings identical; z undefined, skip metric
--
-- Combined arousal score across available metrics. Note the sign:
--   HR up, EDA up, temp up   -> more aroused  (+z)
--   HRV up, SpO2 up          -> less aroused  (-z)
--
--   raw = (z_hr + z_eda + z_temp - z_hrv - z_spo2) / metrics_used
--   score = 1 / (1 + exp(-raw))        -- squash to 0-1
--
--   score < 0.4  -> 'calm'
--   0.4 to 0.7   -> 'elevated'
--   > 0.7        -> 'high'


-- =====================================================================
-- 10. SEED DATA
-- =====================================================================

INSERT INTO categories (code, label, identity_level, price_level,
                        advertising_level, distribution_level,
                        marketing_score) VALUES
 ('groceries',   'Groceries',   'low',  'low',  'high', 'high', 0.75),
 ('clothing',    'Clothing',    'high', 'mid',  'high', 'mid',  1.00),
 ('restaurant',  'Restaurant',  'low',  'low',  'mid',  'high', 0.50),
 ('electronics', 'Electronics', 'mid',  'high', 'high', 'mid',  0.00),
 ('mall',        'Mall',        'high', 'mid',  'high', 'mid',  1.00),
 ('online',      'Online',      'mid',  'low',  'high', 'high', 0.75),
 ('other',       'Other',       'mid',  'mid',  'mid',  'mid',  0.25);

-- Derived marketing-stimuli score. Weight directions follow the
-- meta-analysis; the magnitudes are a project decision and should be
-- documented as such.
UPDATE categories SET stimuli_score = ROUND((
      (CASE identity_level     WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END)
    - (CASE price_level        WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END)
    - (CASE distribution_level WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END) * 0.5
    + (CASE advertising_level  WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END) * 0.5
    + 0.25)::numeric, 2);

-- =====================================================================
-- Wellness & spending app - database schema (v3)
-- Plain PostgreSQL 16.
--
-- Data model: the user manually enters physiological readings at a
-- check-in immediately before a transaction. Mean and standard
-- deviation are NOT entered - they are computed per user across that
-- user's accumulated check-in history. A given reading is then scored
-- as a z-score against that user's own baseline.
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
    stimuli_score       REAL     -- derived, 0-1; see section 8
);


-- =====================================================================
-- 4. CHECK-IN  (the core table)
--
-- One row per pre-transaction check-in. Every physiological value is
-- entered by the user. All are nullable: the user may not have every
-- reading available, and a check-in with only some values is still
-- useful.
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
    checkin_type        TEXT NOT NULL DEFAULT 'pre_transaction',  -- 'pre_transaction' | 'standalone'

    -- manually entered physiological readings
    heart_rate          REAL CHECK (heart_rate BETWEEN 30 AND 220),
    hrv_ms              REAL CHECK (hrv_ms BETWEEN 1 AND 300),
    eda_microsiemens    REAL CHECK (eda_microsiemens BETWEEN 0 AND 100),
    spo2_percent        REAL CHECK (spo2_percent BETWEEN 70 AND 100),
    skin_temp_c         REAL CHECK (skin_temp_c BETWEEN 30 AND 43),
    eeg_value           REAL,

    entered_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- at least one reading must be present
    CONSTRAINT at_least_one_reading CHECK (
        heart_rate IS NOT NULL OR hrv_ms IS NOT NULL
        OR eda_microsiemens IS NOT NULL OR spo2_percent IS NOT NULL
        OR skin_temp_c IS NOT NULL OR eeg_value IS NOT NULL
    )
);
CREATE INDEX ON checkins (user_id, entered_at DESC);


-- =====================================================================
-- 5. BASELINE
--
-- Mean and standard deviation per user per metric, computed across
-- that user's check-in history. Refreshed after each new check-in.
-- This is what makes a reading interpretable: 82 bpm means nothing
-- until you know that this person's own mean is 71 with an sd of 6.
--
-- sample_n matters: with fewer than about 8 check-ins the standard
-- deviation is unstable and should not be used for scoring.
-- =====================================================================

CREATE TABLE user_baseline (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    metric          TEXT NOT NULL,   -- 'heart_rate' | 'hrv_ms' | ...
    mean_value      REAL NOT NULL,
    sd_value        REAL,            -- null until sample_n >= 2
    sample_n        INTEGER NOT NULL,
    min_value       REAL,
    max_value       REAL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, metric)
);


-- =====================================================================
-- 6. AROUSAL
--
-- Derived from a check-in by comparing each reading to the user's
-- baseline. One row per check-in.
-- =====================================================================

CREATE TYPE arousal_label AS ENUM ('calm', 'elevated', 'high', 'unknown');

CREATE TABLE arousal_state (
    id                  BIGSERIAL PRIMARY KEY,
    checkin_id          BIGINT NOT NULL UNIQUE REFERENCES checkins(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- per-metric z-scores: (reading - user mean) / user sd
    z_heart_rate        REAL,
    z_hrv               REAL,
    z_eda               REAL,
    z_spo2              REAL,
    z_skin_temp         REAL,

    score               REAL CHECK (score BETWEEN 0 AND 1),
    label               arousal_label NOT NULL DEFAULT 'unknown',
    confidence          REAL CHECK (confidence BETWEEN 0 AND 1),
    metrics_used        SMALLINT NOT NULL,   -- how many z-scores were computable
    model_version       TEXT NOT NULL,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON arousal_state (user_id, computed_at DESC);


-- =====================================================================
-- 7. TRANSACTIONS
--
-- BOUNDARY: nothing in this section is read by the arousal scorer.
-- Arousal is computed from physiology alone. Spending is analysed
-- against arousal, never used to produce it.
-- =====================================================================

CREATE TABLE transactions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    checkin_id      BIGINT REFERENCES checkins(id),  -- the check-in that preceded it
    amount          NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    currency        TEXT NOT NULL DEFAULT 'LBP',
    category_code   TEXT NOT NULL REFERENCES categories(code),
    merchant_name   TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    was_planned     BOOLEAN,          -- optional self-report
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON transactions (user_id, occurred_at DESC);
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

CREATE TABLE user_settings (
    user_id                     UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    quiet_hours_start           TIME NOT NULL DEFAULT '22:00',
    quiet_hours_end             TIME NOT NULL DEFAULT '08:00',
    max_notifs_per_day          SMALLINT NOT NULL DEFAULT 3,
    notifications_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    notifications_muted_until   TIMESTAMPTZ,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

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


-- =====================================================================
-- 9. HOW TO COMPUTE MEAN AND STANDARD DEVIATION
--
-- Run after every new check-in, for the user who just checked in.
-- stddev_samp() is the sample standard deviation (n-1 denominator),
-- which is correct here. It returns NULL when there is only one row.
-- =====================================================================

-- Refresh one metric for one user:
--
-- INSERT INTO user_baseline (user_id, metric, mean_value, sd_value,
--                            sample_n, min_value, max_value, computed_at)
-- SELECT user_id,
--        'heart_rate',
--        avg(heart_rate),
--        stddev_samp(heart_rate),
--        count(heart_rate),
--        min(heart_rate),
--        max(heart_rate)
--        , now()
-- FROM checkins
-- WHERE user_id = :user_id AND heart_rate IS NOT NULL
-- GROUP BY user_id
-- ON CONFLICT (user_id, metric) DO UPDATE
--   SET mean_value  = EXCLUDED.mean_value,
--       sd_value    = EXCLUDED.sd_value,
--       sample_n    = EXCLUDED.sample_n,
--       min_value   = EXCLUDED.min_value,
--       max_value   = EXCLUDED.max_value,
--       computed_at = EXCLUDED.computed_at;
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
                        advertising_level, distribution_level) VALUES
 ('groceries',   'Groceries',   'low',  'low',  'high', 'high'),
 ('clothing',    'Clothing',    'high', 'mid',  'high', 'mid'),
 ('restaurant',  'Restaurant',  'low',  'low',  'mid',  'high'),
 ('electronics', 'Electronics', 'mid',  'high', 'high', 'mid'),
 ('mall',        'Mall',        'high', 'mid',  'high', 'mid'),
 ('online',      'Online',      'mid',  'low',  'high', 'high'),
 ('other',       'Other',       'mid',  'mid',  'mid',  'mid');

-- Derived marketing-stimuli score. Weight directions follow the
-- meta-analysis; the magnitudes are a project decision and should be
-- documented as such.
UPDATE categories SET stimuli_score = ROUND((
      (CASE identity_level     WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END)
    - (CASE price_level        WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END)
    - (CASE distribution_level WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END) * 0.5
    + (CASE advertising_level  WHEN 'low' THEN 0 WHEN 'mid' THEN 0.5 ELSE 1 END) * 0.5
    + 0.25)::numeric, 2);

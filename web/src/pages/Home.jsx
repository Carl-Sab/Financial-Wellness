import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Button from "../components/Button";
import { buildEcgPath } from "../components/landing/ecgPath";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import { formatMoney } from "../lib/currency";
import "../components/landing/Header.css";
import "./Home.css";

const ECG_PATH = buildEcgPath({ width: 640, height: 48, cycles: 4 });
const CHECKIN_MARK_PATH = buildEcgPath({ width: 64, height: 28, cycles: 1 });

// Quiet, line-drawn identifying marks in each card's corner — a texture,
// not an icon set, so they stay low-contrast (opacity handled in CSS) and
// never carry meaning on their own.
function CheckinMark() {
  return (
    <svg className="card__mark" viewBox="0 0 64 28" aria-hidden="true">
      <path d={CHECKIN_MARK_PATH} />
    </svg>
  );
}

function StatisticsMark() {
  return (
    <svg className="card__mark" viewBox="0 0 40 32" aria-hidden="true">
      <line x1="8" y1="28" x2="8" y2="16" />
      <line x1="20" y1="28" x2="20" y2="6" />
      <line x1="32" y1="28" x2="32" y2="20" />
    </svg>
  );
}

function BankMark() {
  return (
    <svg className="card__mark" viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r="15" />
      <circle cx="20" cy="20" r="8" />
    </svg>
  );
}

async function fetchWeeklyHeartRateAverage() {
  const response = await apiFetch("/api/v1/samples/averages?period=week");
  if (!response.ok) throw new Error("Failed to load statistics");
  const buckets = await response.json();
  // Ascending order (see samples.py) — the last bucket is the current week.
  return buckets.length > 0 ? buckets[buckets.length - 1] : null;
}

async function fetchSpendingSummary() {
  const response = await apiFetch("/api/v1/spending/summary");
  if (!response.ok) throw new Error("Failed to load bank summary");
  return response.json();
}

// Each card owns its own loading/error/data cycle — one card's fetch
// failing must never block or blank the other two. loadFn is a stable
// module-level function (no props/closures to worry about), so `attempt`
// alone is enough to drive re-fetching on retry.
function useCardData(loadFn) {
  const [status, setStatus] = useState("loading"); // loading | error | success
  const [data, setData] = useState(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    loadFn()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setStatus("success");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  return { status, data, retry: () => setAttempt((a) => a + 1) };
}

function scrollToCard(id) {
  return (event) => {
    event.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
}

function CardError({ onRetry }) {
  return (
    <div className="card__error" role="alert">
      <p>Couldn&rsquo;t load this.</p>
      <button type="button" className="card__retry" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

function StatisticsPreview({ status, data, retry }) {
  if (status === "loading") {
    return (
      <div className="card__skeleton" aria-hidden="true">
        <span className="skeleton skeleton--line-lg" />
        <span className="skeleton skeleton--line-sm" />
      </div>
    );
  }

  if (status === "error") {
    return <CardError onRetry={retry} />;
  }

  if (data == null || data.avg_heart_rate == null) {
    return <p className="card__empty">No readings yet</p>;
  }

  return (
    <p className="card__stat">
      <span className="card__stat-value">{Math.round(data.avg_heart_rate)}</span>
      <span className="card__stat-unit">bpm avg this week</span>
    </p>
  );
}

function BankPreview({ status, data, retry }) {
  if (status === "loading") {
    return (
      <div className="card__skeleton" aria-hidden="true">
        <span className="skeleton skeleton--line-lg" />
        <span className="skeleton skeleton--line-sm" />
        <span className="skeleton skeleton--bar" />
      </div>
    );
  }

  if (status === "error") {
    return <CardError onRetry={retry} />;
  }

  const { currency, daily, weekly, monthly, balance } = data;
  const hasMonthlyTarget = monthly.target != null && Number(monthly.target) > 0;
  const isOverBudget = hasMonthlyTarget && Number(monthly.spent) > Number(monthly.target);
  const progressPct = hasMonthlyTarget
    ? Math.min(100, (Number(monthly.spent) / Number(monthly.target)) * 100)
    : 0;

  return (
    <div className="bank-preview">
      <p className="bank-preview__balance">{formatMoney(balance, currency)}</p>
      <p className="bank-preview__balance-label">Balance</p>

      <div className="bank-preview__monthly">
        <div className="bank-preview__monthly-row">
          <span>This month</span>
          <span>
            {formatMoney(monthly.spent, currency)}
            {hasMonthlyTarget && <> of {formatMoney(monthly.target, currency)}</>}
          </span>
        </div>
        {hasMonthlyTarget ? (
          <div
            className="bank-preview__progress"
            role="progressbar"
            aria-valuenow={Math.round(progressPct)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Monthly budget used"
          >
            <div
              className={`bank-preview__progress-fill ${isOverBudget ? "bank-preview__progress-fill--over" : ""}`}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        ) : (
          <p className="card__empty card__empty--tight">No monthly budget set</p>
        )}
      </div>

      <div className="bank-preview__figures">
        <div>
          <p className="bank-preview__figure-value">{formatMoney(weekly.spent, currency)}</p>
          <p className="bank-preview__figure-label">This week</p>
        </div>
        <div>
          <p className="bank-preview__figure-value">{formatMoney(daily.spent, currency)}</p>
          <p className="bank-preview__figure-label">Today</p>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const statistics = useCardData(fetchWeeklyHeartRateAverage);
  const bank = useCardData(fetchSpendingSummary);

  const firstName = user?.full_name?.trim().split(/\s+/)[0] ?? "";

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  return (
    <div className="home">
      <header className="header header--scrolled">
        <div className="header__inner">
          <span className="header__logo">Financial&nbsp;Wellness</span>

          <nav className="header__nav" aria-label="Primary">
            <a href="#checkin-card" className="header__link" onClick={scrollToCard("checkin-card")}>
              Check in
            </a>
            <a
              href="#statistics-card"
              className="header__link"
              onClick={scrollToCard("statistics-card")}
            >
              Statistics
            </a>
            <a href="#bank-card" className="header__link" onClick={scrollToCard("bank-card")}>
              Bank
            </a>
            <Button variant="secondary" className="header__login" onClick={handleLogout}>
              Log out
            </Button>
          </nav>
        </div>
      </header>

      <main className="home__content">
        {firstName && (
          <div className="home__intro">
            <h1 className="home__greeting">Welcome back, {firstName}.</h1>
            <p className="home__subhead">Your body and your budget, side by side.</p>
            <div className="home__ecg" aria-hidden="true">
              <svg viewBox="0 0 640 48" preserveAspectRatio="none" className="home__ecg-svg">
                <path d={ECG_PATH} pathLength="1" className="home__ecg-path" />
              </svg>
            </div>
          </div>
        )}

        <div className="home__cards">
          <section id="checkin-card" className="card card--primary">
            <CheckinMark />
            <h2 className="card__title">Start a check-in</h2>
            <p className="card__body">Record how you&rsquo;re feeling before a purchase.</p>
            <Button as="link" to="/checkin" variant="dark" className="card__cta">
              Check in
            </Button>
          </section>

          <section id="statistics-card" className="card">
            <StatisticsMark />
            <h2 className="card__title">Statistics</h2>
            <StatisticsPreview {...statistics} />
            <Button as="link" to="/statistics" variant="dark" className="card__cta">
              View statistics
            </Button>
          </section>

          <section id="bank-card" className="card">
            <BankMark />
            <h2 className="card__title">Bank</h2>
            <BankPreview {...bank} />
            <Button as="link" to="/bank" variant="dark" className="card__cta">
              View bank
            </Button>
          </section>
        </div>
      </main>
    </div>
  );
}

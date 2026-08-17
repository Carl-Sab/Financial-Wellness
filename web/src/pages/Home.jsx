import { useNavigate } from "react-router-dom";
import Button from "../components/Button";
import { buildEcgPath } from "../components/landing/ecgPath";
import { useAuth } from "../context/AuthContext";
import { useCardData } from "../hooks/useCardData";
import { useDisplayCurrency } from "../hooks/useDisplayCurrency";
import { apiFetch } from "../lib/api";
import { convertAmount, formatMoney } from "../lib/currency";
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

function GoalsMark() {
  return (
    <svg className="card__mark" viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r="15" />
      <path d="M20 10 L20 20 L27 24" />
    </svg>
  );
}

async function fetchWeeklyStatistics() {
  const response = await apiFetch(
    "/api/v1/analysis/statistics?view=weekly&category_view=daily"
  );
  if (!response.ok) throw new Error("Failed to load statistics");
  return response.json();
}

async function fetchSpendingSummary() {
  const response = await apiFetch("/api/v1/spending/summary");
  if (!response.ok) throw new Error("Failed to load bank summary");
  return response.json();
}

async function fetchMonthlyGoal() {
  const response = await apiFetch("/api/v1/goals/monthly/current");
  if (!response.ok) throw new Error("Failed to load monthly goal");
  return response.json();
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

function StatisticsPreview({ status, data, retry, displayCurrency }) {
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

  const spent = data.review.reduce(
    (total, bucket) => total + Number(bucket.spent_amount),
    0
  );
  const budget = data.review.reduce(
    (total, bucket) => total + Number(bucket.budget_amount),
    0
  );
  const displayedSpent = convertAmount(spent, data.currency, displayCurrency);
  const displayedBudget = convertAmount(budget, data.currency, displayCurrency);
  const percentage = budget > 0 ? (spent / budget) * 100 : null;

  if (spent === 0) return <p className="card__empty">No spending recorded this week</p>;

  return (
    <div className="statistics-preview">
      <p className="card__stat statistics-preview__headline">
        <span className="card__stat-value">
          {percentage == null
            ? formatMoney(displayedSpent, displayCurrency)
            : `${Math.round(percentage)}%`}
        </span>
        <span className="card__stat-unit">
          {percentage == null ? "spent this week" : "of weekly budget"}
        </span>
      </p>
      {percentage != null && (
        <>
          <p className="statistics-preview__amounts">
            {formatMoney(displayedSpent, displayCurrency)} spent of {formatMoney(
              displayedBudget,
              displayCurrency
            )}
          </p>
          <div
            className="statistics-preview__progress"
            role="progressbar"
            aria-label="Weekly budget used"
            aria-valuenow={Math.min(100, Math.round(percentage))}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className={`statistics-preview__progress-fill ${
                percentage > 100 ? "statistics-preview__progress-fill--over" : ""
              }`}
              style={{ width: `${Math.min(100, percentage)}%` }}
            />
          </div>
        </>
      )}
    </div>
  );
}

// One bar for one window (daily/weekly/monthly) — same fill/over-budget
// math the app has always used for the monthly bar, just parameterized so
// it can be reused three times instead of hardcoded to one window.
function SpendingBar({ label, emptyLabel, window, sourceCurrency, displayCurrency }) {
  const spent = convertAmount(window.spent, sourceCurrency, displayCurrency);
  const target =
    window.target != null ? convertAmount(window.target, sourceCurrency, displayCurrency) : null;
  const hasTarget = target != null && target > 0;
  const isOverBudget = hasTarget && spent > target;
  const progressPct = hasTarget ? Math.min(100, (spent / target) * 100) : 0;

  return (
    <div className="bank-preview__window">
      <div className="bank-preview__window-row">
        <span>{label}</span>
        <span>
          {formatMoney(spent, displayCurrency)}
          {hasTarget && <> of {formatMoney(target, displayCurrency)}</>}
        </span>
      </div>
      {hasTarget ? (
        <div
          className="bank-preview__progress"
          role="progressbar"
          aria-valuenow={Math.round(progressPct)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label} budget used`}
        >
          <div
            className={`bank-preview__progress-fill ${isOverBudget ? "bank-preview__progress-fill--over" : ""}`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      ) : (
        <p className="card__empty card__empty--tight">{emptyLabel}</p>
      )}
    </div>
  );
}

function GoalsPreview({ status, data, retry, displayCurrency }) {
  if (status === "loading") {
    return (
      <div className="card__skeleton" aria-hidden="true">
        <span className="skeleton skeleton--line-lg" />
        <span className="skeleton skeleton--bar" />
      </div>
    );
  }

  if (status === "error") {
    return <CardError onRetry={retry} />;
  }

  if (data.status === "needs_setup") {
    return <p className="card__empty">Set your goal for this month</p>;
  }

  const { progress } = data;
  const target = Number(progress.target_amount);
  const spent = Number(progress.spent_amount);
  const percentage = target > 0 ? (spent / target) * 100 : null;
  const displayedSpent = convertAmount(spent, data.goal.currency, displayCurrency);

  return (
    <div className="statistics-preview">
      <p className="card__stat statistics-preview__headline">
        <span className="card__stat-value">
          {percentage == null
            ? formatMoney(displayedSpent, displayCurrency)
            : `${Math.round(percentage)}%`}
        </span>
        <span className="card__stat-unit">
          {percentage == null ? "spent this month" : "of monthly goal"}
        </span>
      </p>
      {percentage != null && (
        <div
          className="statistics-preview__progress"
          role="progressbar"
          aria-label="Monthly goal used"
          aria-valuenow={Math.min(100, Math.round(percentage))}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className={`statistics-preview__progress-fill ${
              progress.is_over ? "statistics-preview__progress-fill--over" : ""
            }`}
            style={{ width: `${Math.min(100, percentage)}%` }}
          />
        </div>
      )}
    </div>
  );
}

function CurrencyToggle({ value, onChange }) {
  return (
    <div className="bank-preview__currency-toggle" role="radiogroup" aria-label="Display currency">
      {["LBP", "USD"].map((code) => (
        <button
          key={code}
          type="button"
          role="radio"
          aria-checked={value === code}
          className={`bank-preview__currency-toggle-option ${
            value === code ? "bank-preview__currency-toggle-option--selected" : ""
          }`}
          onClick={() => onChange(code)}
        >
          {code === "USD" ? "$" : "L.L."}
        </button>
      ))}
    </div>
  );
}

function BankPreview({ status, data, retry, displayCurrency, onDisplayCurrencyChange }) {
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
  const displayedBalance = convertAmount(balance, currency, displayCurrency);

  return (
    <div className="bank-preview">
      <CurrencyToggle value={displayCurrency} onChange={onDisplayCurrencyChange} />

      <p className="bank-preview__balance">{formatMoney(displayedBalance, displayCurrency)}</p>
      <p className="bank-preview__balance-label">Balance</p>

      <div className="bank-preview__windows">
        <SpendingBar
          label="This month"
          emptyLabel="No monthly budget set"
          window={monthly}
          sourceCurrency={currency}
          displayCurrency={displayCurrency}
        />
        <SpendingBar
          label="This week"
          emptyLabel="No weekly budget set"
          window={weekly}
          sourceCurrency={currency}
          displayCurrency={displayCurrency}
        />
        <SpendingBar
          label="Today"
          emptyLabel="No daily budget set"
          window={daily}
          sourceCurrency={currency}
          displayCurrency={displayCurrency}
        />
      </div>
    </div>
  );
}

export default function Home() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const statistics = useCardData(fetchWeeklyStatistics);
  const bank = useCardData(fetchSpendingSummary);
  const goal = useCardData(fetchMonthlyGoal);
  const [displayCurrency, setDisplayCurrency] = useDisplayCurrency();

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
            <StatisticsPreview {...statistics} displayCurrency={displayCurrency} />
            <Button as="link" to="/statistics" variant="dark" className="card__cta">
              View statistics
            </Button>
          </section>

          <section id="bank-card" className="card">
            <BankMark />
            <h2 className="card__title">Bank</h2>
            <BankPreview
              {...bank}
              displayCurrency={displayCurrency}
              onDisplayCurrencyChange={setDisplayCurrency}
            />
            <Button as="link" to="/bank" variant="dark" className="card__cta">
              View bank
            </Button>
          </section>

          <section id="goals-card" className="card">
            <GoalsMark />
            <h2 className="card__title">Goals</h2>
            <GoalsPreview {...goal} displayCurrency={displayCurrency} />
            <Button as="link" to="/goals" variant="dark" className="card__cta">
              View goal
            </Button>
          </section>
        </div>
      </main>
    </div>
  );
}

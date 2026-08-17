import { useRef, useState } from "react";
import Button from "../components/Button";
import { useCardData } from "../hooks/useCardData";
import { apiFetch } from "../lib/api";
import { currencySymbol, formatMoney } from "../lib/currency";
import "./Signup.css";
import "./Questionnaire.css";
import "./OnboardingBudget.css";
import "./Goals.css";

async function fetchMonthlyGoal() {
  const response = await apiFetch("/api/v1/goals/monthly/current");
  if (!response.ok) throw new Error("Failed to load monthly goal");
  return response.json();
}

const SUGGESTION_COPY = {
  reduce_from_overspend: (spent, currency) =>
    `Last month you spent ${formatMoney(spent, currency)}, over budget. Try 20% less.`,
  tighten_from_underspend: (spent, currency) =>
    `Last month you spent ${formatMoney(spent, currency)}, under budget. Here's a tighter goal.`,
};

function GoalProgressBar({ progress, currency }) {
  const { target_amount, spent_amount, is_over, overage_amount } = progress;
  const target = Number(target_amount);
  const spent = Number(spent_amount);
  const fillPct = target > 0 ? Math.min(100, (spent / target) * 100) : 0;
  // Overage is shown as its own distinct segment past the bar, not folded
  // into a clamped-at-100% fill — the whole point is that going over reads
  // differently from being on track, not just "full."
  const overagePct = is_over && target > 0 ? Math.min(100, (Number(overage_amount) / target) * 100) : 0;

  return (
    <div className="goal-progress">
      <div
        className="goal-progress__track"
        role="progressbar"
        aria-label="Monthly goal progress"
        aria-valuenow={Math.round(fillPct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="goal-progress__fill" style={{ width: `${fillPct}%` }} />
        {is_over && <div className="goal-progress__overage" style={{ width: `${overagePct}%` }} />}
      </div>
      {is_over && (
        <p className="goal-progress__overage-label" role="alert">
          {formatMoney(overage_amount, currency)} over this month's goal
        </p>
      )}
    </div>
  );
}

function ActiveGoal({ goal, progress, onGoalChanged }) {
  return (
    <div className="goals-card">
      <p className="goals-card__eyebrow">This month's goal</p>
      <p className="goals-card__amount">{formatMoney(goal.target_amount, goal.currency)}</p>
      <GoalProgressBar progress={progress} currency={goal.currency} />
      <p className="goals-card__detail">
        {formatMoney(progress.spent_amount, goal.currency)} spent of{" "}
        {formatMoney(progress.target_amount, goal.currency)}
      </p>
    </div>
  );
}

function NeedsSetup({ suggestion, onGoalChanged }) {
  const [customValue, setCustomValue] = useState("");
  const [currency, setCurrency] = useState(suggestion.currency);
  const [touched, setTouched] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | loading | error
  const isSubmittingRef = useRef(false);

  const symbol = currencySymbol(currency);
  const numericValue = Number(customValue);
  const isValid = customValue.trim() !== "" && Number.isFinite(numericValue) && numericValue > 0;
  const showError = touched && !isValid;

  async function submit(body) {
    if (isSubmittingRef.current) return;
    isSubmittingRef.current = true;
    setStatus("loading");
    try {
      const response = await apiFetch("/api/v1/goals/monthly", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (response.status === 201) {
        onGoalChanged();
        return;
      }
      setStatus("error");
    } catch {
      setStatus("error");
    } finally {
      isSubmittingRef.current = false;
    }
  }

  function handleAccept() {
    submit({ accept_suggestion: true });
  }

  function handleCustomSubmit(event) {
    event.preventDefault();
    if (!isValid) {
      setTouched(true);
      return;
    }
    submit({ target_amount: customValue, currency });
  }

  const isLoading = status === "loading";
  const copy = SUGGESTION_COPY[suggestion.basis] ?? SUGGESTION_COPY.tighten_from_underspend;

  return (
    <div className="goals-card goals-card--setup">
      <p className="goals-card__eyebrow">Set this month's goal</p>
      <p className="questionnaire__intro">{copy(suggestion.amount, suggestion.currency)}</p>

      <p className="goals-card__amount">{formatMoney(suggestion.amount, suggestion.currency)}</p>
      <Button variant="dark" onClick={handleAccept} disabled={isLoading} className="goals-card__accept">
        {isLoading ? "Saving…" : "Use this amount"}
      </Button>

      <p className="goals-card__or">or set your own</p>

      <form onSubmit={handleCustomSubmit} noValidate>
        <div className="budget-currency-toggle" role="radiogroup" aria-label="Goal currency">
          {["LBP", "USD"].map((code) => (
            <button
              key={code}
              type="button"
              role="radio"
              aria-checked={currency === code}
              className={`budget-currency-toggle__option ${
                currency === code ? "budget-currency-toggle__option--selected" : ""
              }`}
              onClick={() => setCurrency(code)}
            >
              {code}
            </button>
          ))}
        </div>

        <div className="field">
          <label htmlFor="custom-goal" className="field__label">
            Custom monthly goal
          </label>
          <div className="budget__input-wrap">
            <span className="budget__symbol" aria-hidden="true">
              {symbol}
            </span>
            <input
              id="custom-goal"
              type="number"
              inputMode="decimal"
              min="0"
              step="any"
              autoComplete="off"
              className={`field__control budget__input ${showError ? "field__control--error" : ""}`}
              value={customValue}
              onChange={(event) => setCustomValue(event.target.value)}
              onBlur={() => setTouched(true)}
              aria-invalid={showError ? "true" : undefined}
            />
          </div>
          {showError && (
            <p className="field__error" role="alert">
              Enter an amount greater than {symbol}0
            </p>
          )}
        </div>

        {status === "error" && (
          <p className="questionnaire__form-error" role="alert">
            Couldn&rsquo;t reach the server. Nothing you entered was lost.
          </p>
        )}

        <button type="submit" className="btn btn--primary" disabled={isLoading}>
          {isLoading ? "Saving…" : "Set goal"}
        </button>
      </form>
    </div>
  );
}

export default function Goals() {
  const { status, data, retry } = useCardData(fetchMonthlyGoal);

  return (
    <div className="questionnaire goals-page">
      <div className="questionnaire__content">
        <h1 className="questionnaire__title">Monthly goal</h1>

        {status === "loading" && <p className="card__empty">Loading…</p>}

        {status === "error" && (
          <div className="card__error" role="alert">
            <p>Couldn&rsquo;t load this.</p>
            <button type="button" className="card__retry" onClick={retry}>
              Try again
            </button>
          </div>
        )}

        {status === "success" && data.status === "active" && (
          <ActiveGoal goal={data.goal} progress={data.progress} onGoalChanged={retry} />
        )}

        {status === "success" && data.status === "needs_setup" && (
          <NeedsSetup suggestion={data.suggestion} onGoalChanged={retry} />
        )}
      </div>
    </div>
  );
}

import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import Button from "../components/Button";
import { apiFetch } from "../lib/api";
import { currencySymbol, formatMoney } from "../lib/currency";
import ArousalSliderField from "./ArousalSliderField";
import {
  AROUSAL_QUESTION,
  CATEGORIES,
  CATEGORY_QUESTION,
  DETAILED_AROUSAL,
  DETAILED_AROUSAL_HINT,
  QUICK_AROUSAL,
  QUICK_AROUSAL_HINT,
  VALENCE_LEVELS,
  VALENCE_QUESTION,
} from "./checkinItems";
import "./Signup.css";
import "./Questionnaire.css";
import "./Checkin.css";

// A UI preference, not auth state — plain localStorage, no backend round
// trip needed to remember which mode they used last time.
const MODE_STORAGE_KEY = "checkin.mode";

function loadStoredMode() {
  try {
    const stored = localStorage.getItem(MODE_STORAGE_KEY);
    return stored === "detailed" ? "detailed" : "quick"; // quick is the default
  } catch {
    return "quick"; // localStorage can throw (private browsing, quota) — never block the form on it
  }
}

function storeMode(mode) {
  try {
    localStorage.setItem(MODE_STORAGE_KEY, mode);
  } catch {
    // Non-fatal — the choice just won't persist this time.
  }
}

function initialDetailedArousal() {
  return Object.fromEntries(DETAILED_AROUSAL.map((item) => [item.field, 0]));
}

// form: the check-in questions. prediction: the live model result.
// amount: the transaction amount. success: recorded.
const STAGES = ["form", "prediction", "amount", "success"];

async function apiErrorMessage(response, fallback) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((issue) => {
          const field = Array.isArray(issue.loc)
            ? issue.loc.filter((part) => part !== "body").join(".")
            : "";
          return field ? `${field}: ${issue.msg}` : issue.msg;
        })
        .join(" ");
    }
  } catch {
    // The fallback is still useful when the response has no JSON body.
  }
  return fallback;
}

export default function Checkin() {
  const [stageIndex, setStageIndex] = useState(0);
  const [category, setCategory] = useState(null);
  const [valenceIndex, setValenceIndex] = useState(null);
  const [mode, setMode] = useState(loadStoredMode);
  // Both modes keep their own values, so switching modes does not discard
  // what the user already selected. Sliders default to the neutral value 0.
  const [quickArousal, setQuickArousal] = useState(0);
  const [detailedArousal, setDetailedArousal] = useState(initialDetailedArousal);
  const [checkinId, setCheckinId] = useState(null);
  const [checkinSubmitStatus, setCheckinSubmitStatus] = useState("idle"); // idle | loading | error
  const [checkinSubmitError, setCheckinSubmitError] = useState("");
  const [prediction, setPrediction] = useState(null);
  const [predictionStatus, setPredictionStatus] = useState("idle"); // idle | loading | error
  const [predictionError, setPredictionError] = useState("");
  const [amount, setAmount] = useState("");
  const [amountTouched, setAmountTouched] = useState(false);
  // Independent of the account's default currency (users.currency) — same
  // pattern as the onboarding budget's own LBP/USD toggle: a purchase can
  // be paid in either, regardless of what the account defaults to.
  const [currency, setCurrency] = useState("LBP");
  const [submitStatus, setSubmitStatus] = useState("idle"); // idle | loading | error
  // Same double-submit guard used across the app's other forms: a ref,
  // because React batches state updates, so two synchronous taps could
  // both still read "not submitted" before either update commits.
  const isSubmittingRef = useRef(false);

  const stage = STAGES[stageIndex];
  const visibleArousalItems = mode === "quick" ? [QUICK_AROUSAL] : DETAILED_AROUSAL;
  const canSubmitCheckin = category != null && valenceIndex != null;
  const amountNumber = Number(amount);
  const amountValid = amount.trim() !== "" && Number.isFinite(amountNumber) && amountNumber > 0;

  function handleModeChange(nextMode) {
    setMode(nextMode);
    storeMode(nextMode);
  }

  function handleArousalChange(field, value) {
    if (mode === "quick") {
      setQuickArousal(value);
      return;
    }
    setDetailedArousal((current) => ({ ...current, [field]: value }));
  }

  async function loadPrediction(id) {
    setPrediction(null);
    setPredictionStatus("loading");
    setPredictionError("");

    try {
      const response = await apiFetch(`/api/v1/checkins/${id}/prediction`, {
        method: "POST",
      });

      if (!response.ok) {
        setPredictionError(
          await apiErrorMessage(response, "The server could not calculate the risk right now."),
        );
        setPredictionStatus("error");
        return;
      }

      setPrediction(await response.json());
      setPredictionStatus("idle");
    } catch {
      setPredictionError("Could not reach the prediction service.");
      setPredictionStatus("error");
    }
  }

  async function retryPrediction() {
    if (isSubmittingRef.current || checkinId == null) return;
    isSubmittingRef.current = true;
    try {
      await loadPrediction(checkinId);
    } finally {
      isSubmittingRef.current = false;
    }
  }

  async function submitCheckin() {
    if (isSubmittingRef.current) return;
    if (!canSubmitCheckin) {
      return;
    }
    isSubmittingRef.current = true;
    setCheckinSubmitStatus("loading");
    setCheckinSubmitError("");

    try {
      const response = await apiFetch("/api/v1/checkins", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category_code: category,
          valence: VALENCE_LEVELS[valenceIndex].valence,
          ...(mode === "quick"
            ? { arousal_input_mode: "manual", arousal_z: quickArousal }
            : { arousal_input_mode: "detailed", ...detailedArousal }),
        }),
      });

      if (!response.ok) {
        setCheckinSubmitError(
          await apiErrorMessage(response, "The server rejected this check-in."),
        );
        setCheckinSubmitStatus("error");
        return;
      }

      const checkin = await response.json();
      setCheckinId(checkin.id);
      setCheckinSubmitStatus("idle");
      setStageIndex(1); // -> prediction
      await loadPrediction(checkin.id);
    } catch {
      setCheckinSubmitError("Could not reach the server. Nothing you entered was lost.");
      setCheckinSubmitStatus("error");
    } finally {
      isSubmittingRef.current = false;
    }
  }

  function handleCheckinSubmit(event) {
    event.preventDefault();
    submitCheckin();
  }

  function handleContinueToAmount() {
    if (prediction == null) return;
    setStageIndex(2); // -> amount. The prediction never blocks this.
  }

  function handleBack() {
    setStageIndex((i) => Math.max(0, i - 1));
  }

  async function submitTransaction() {
    if (isSubmittingRef.current) return;
    if (!amountValid) {
      setAmountTouched(true);
      return;
    }
    isSubmittingRef.current = true;
    setSubmitStatus("loading");

    try {
      // occurred_at is left unset — the server stamps it with the current
      // time, which is exactly the purchase date/time we want recorded.
      const response = await apiFetch("/api/v1/transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: amountNumber,
          currency,
          category_code: category,
          checkin_id: checkinId,
        }),
      });

      if (!response.ok) {
        setSubmitStatus("error");
        return;
      }

      setSubmitStatus("idle");
      setStageIndex(3); // -> success
    } catch {
      setSubmitStatus("error");
    } finally {
      isSubmittingRef.current = false;
    }
  }

  function handleAmountSubmit(event) {
    event.preventDefault();
    submitTransaction();
  }

  if (stage === "success") {
    return (
      <div className="checkin">
        <div className="checkin__success">
          <p className="checkin__success-mark" aria-hidden="true">
            ✓
          </p>
          <h1 className="checkin__success-title">Purchase recorded</h1>
          <p className="checkin__success-body">
            Saved with today&rsquo;s date — you&rsquo;ll see it in your bank history.
          </p>
          <Button as="link" to="/home" variant="dark">
            Back to home
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="checkin">
      <div className="checkin__topbar">
        {stage === "form" ? (
          <Link to="/home" className="checkin__back">
            &larr; Home
          </Link>
        ) : (
          <button type="button" className="checkin__back" onClick={handleBack}>
            &larr; Back
          </button>
        )}
      </div>

      <div className="checkin__content">
        <h1 className="checkin__title">Check-in</h1>

        {stage === "form" && (
          <form onSubmit={handleCheckinSubmit} noValidate>
            <section className="checkin__section">
              <h2 className="checkin__question">{CATEGORY_QUESTION}</h2>
              <div className="checkin__tiles" role="radiogroup" aria-label={CATEGORY_QUESTION}>
                {CATEGORIES.map((c) => (
                  <button
                    key={c.code}
                    type="button"
                    role="radio"
                    aria-checked={category === c.code}
                    className={`checkin-tile ${category === c.code ? "checkin-tile--selected" : ""}`}
                    onClick={() => setCategory(c.code)}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </section>

            <section className="checkin__section">
              <h2 className="checkin__question">{VALENCE_QUESTION}</h2>
              <div className="checkin__valence" role="radiogroup" aria-label={VALENCE_QUESTION}>
                {VALENCE_LEVELS.map((level, index) => (
                  <button
                    key={level.valence}
                    type="button"
                    role="radio"
                    aria-checked={valenceIndex === index}
                    className={`checkin-valence-option ${valenceIndex === index ? "checkin-valence-option--selected" : ""}`}
                    onClick={() => setValenceIndex(index)}
                  >
                    {level.label}
                  </button>
                ))}
              </div>
            </section>

            <section className="checkin__section">
              <h2 className="checkin__question">{AROUSAL_QUESTION}</h2>

              <div className="checkin-mode-toggle" role="radiogroup" aria-label="Arousal entry mode">
                <button
                  type="button"
                  role="radio"
                  aria-checked={mode === "quick"}
                  className={`checkin-mode-toggle__option ${mode === "quick" ? "checkin-mode-toggle__option--selected" : ""}`}
                  onClick={() => handleModeChange("quick")}
                >
                  Quick
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={mode === "detailed"}
                  className={`checkin-mode-toggle__option ${mode === "detailed" ? "checkin-mode-toggle__option--selected" : ""}`}
                  onClick={() => handleModeChange("detailed")}
                >
                  Detailed
                </button>
              </div>

              <p className="checkin__hint">
                {mode === "quick" ? QUICK_AROUSAL_HINT : DETAILED_AROUSAL_HINT}
              </p>

              <div className="checkin__arousal-fields">
                {visibleArousalItems.map((item) => (
                  <ArousalSliderField
                    key={item.field}
                    item={item}
                    value={mode === "quick" ? quickArousal : detailedArousal[item.field]}
                    onChange={(value) => handleArousalChange(item.field, value)}
                  />
                ))}
              </div>
            </section>

            {checkinSubmitStatus === "error" && (
              <p className="questionnaire__form-error" role="alert">
                {checkinSubmitError}{" "}
                <button type="button" className="questionnaire__retry" onClick={submitCheckin}>
                  Try again
                </button>
              </p>
            )}

            <button
              type="submit"
              className="btn btn--dark checkin__submit"
              disabled={!canSubmitCheckin || checkinSubmitStatus === "loading"}
            >
              {checkinSubmitStatus === "loading" ? "Recording…" : "Done"}
            </button>
          </form>
        )}

        {stage === "prediction" && (
          <section className="checkin__section">
            {predictionStatus === "loading" && (
              <div className="prediction" aria-live="polite">
                <p className="prediction__label">Current overspending risk</p>
                <p className="prediction__context">Calculating from your check-in and budget...</p>
              </div>
            )}

            {predictionStatus === "error" && (
              <div className="prediction prediction--error" role="alert">
                <p className="prediction__label">Prediction unavailable</p>
                <p className="prediction__context">{predictionError}</p>
                <button type="button" className="questionnaire__retry" onClick={retryPrediction}>
                  Try again
                </button>
              </div>
            )}

            {prediction != null && predictionStatus !== "loading" && (
              <>
                <div className={`prediction prediction--${prediction.risk_level}`}>
                  <p className="prediction__label">Current overspending risk</p>
                  <p className="prediction__value">{prediction.overspending_percentage}%</p>
                  <p className="prediction__tier">{prediction.risk_level} risk</p>
                  <p className="prediction__context">{prediction.message}</p>
                </div>
                <button
                  type="button"
                  className="btn btn--dark checkin__submit"
                  onClick={handleContinueToAmount}
                >
                  Continue
                </button>
              </>
            )}
          </section>
        )}

        {stage === "amount" && (
          <form onSubmit={handleAmountSubmit} noValidate>
            <section className="checkin__section">
              <h2 className="checkin__question">How much is the purchase?</h2>

              <div className="checkin-mode-toggle" role="radiogroup" aria-label="Currency">
                <button
                  type="button"
                  role="radio"
                  aria-checked={currency === "LBP"}
                  className={`checkin-mode-toggle__option ${currency === "LBP" ? "checkin-mode-toggle__option--selected" : ""}`}
                  onClick={() => setCurrency("LBP")}
                >
                  LBP
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={currency === "USD"}
                  className={`checkin-mode-toggle__option ${currency === "USD" ? "checkin-mode-toggle__option--selected" : ""}`}
                  onClick={() => setCurrency("USD")}
                >
                  USD
                </button>
              </div>

              <div className="field">
                <label htmlFor="checkin-amount" className="field__label">
                  Amount
                </label>
                <div className="checkin-amount__wrap">
                  <span className="checkin-amount__symbol" aria-hidden="true">
                    {currencySymbol(currency)}
                  </span>
                  <input
                    id="checkin-amount"
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="any"
                    autoComplete="off"
                    autoFocus
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                    onBlur={() => setAmountTouched(true)}
                    className={`field__control checkin-amount__input ${
                      amountTouched && !amountValid ? "field__control--error" : ""
                    }`}
                    aria-invalid={amountTouched && !amountValid ? "true" : undefined}
                    aria-describedby={amountTouched && !amountValid ? "checkin-amount-error" : undefined}
                  />
                </div>
                {amountTouched && !amountValid && (
                  <p id="checkin-amount-error" className="field__error" role="alert">
                    Enter an amount greater than {formatMoney(0, currency)}
                  </p>
                )}
              </div>
            </section>

            {submitStatus === "error" && (
              <p className="questionnaire__form-error" role="alert">
                Couldn&rsquo;t reach the server. Nothing you entered was lost.{" "}
                <button type="button" className="questionnaire__retry" onClick={submitTransaction}>
                  Try again
                </button>
              </p>
            )}

            <button
              type="submit"
              className="btn btn--dark checkin__submit"
              disabled={!amountValid || submitStatus === "loading"}
            >
              {submitStatus === "loading" ? "Recording…" : "Record purchase"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

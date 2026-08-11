import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import Button from "../components/Button";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import { currencySymbol, formatMoney } from "../lib/currency";
import CheckinArousalSlider from "./CheckinArousalSlider";
import CheckinSlider from "./CheckinSlider";
import {
  CATEGORIES,
  CATEGORY_QUESTION,
  QUICK_AROUSAL_QUESTION,
  SLIDERS,
  VALENCE_LEVELS,
  VALENCE_QUESTION,
} from "./checkinItems";
import "./Signup.css";
import "./Questionnaire.css";
import "./Checkin.css";

const SLIDER_DEFAULT = 0.0;
const QUICK_AROUSAL_DEFAULT = 0;

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

// TODO: replace with the real overspend-prediction call once that endpoint
// exists — e.g. POST /api/v1/predictions/overspend with the check-in
// payload below, expecting something like { probability: number } back.
// Edit this value directly to preview the box at low/medium/high — try
// 0.15, 0.5, and 0.85.
const MOCK_OVERSPEND_PROBABILITY = 0.42;

function overspendTier(probability) {
  if (probability < 0.34) return "low";
  if (probability < 0.67) return "medium";
  return "high";
}

const TIER_COPY = {
  low: "This looks in line with how you usually spend.",
  medium: "This purchase has some chance of pushing you past budget this month.",
  high: "This purchase is likely to push you past budget this month.",
};

function initialSliderValues() {
  const values = {};
  for (const slider of SLIDERS) values[slider.field] = SLIDER_DEFAULT;
  return values;
}

// form: the check-in questions. prediction: the mocked result box.
// amount: the transaction amount. success: recorded.
const STAGES = ["form", "prediction", "amount", "success"];

export default function Checkin() {
  const { user } = useAuth();
  const [stageIndex, setStageIndex] = useState(0);
  const [category, setCategory] = useState(null);
  const [valenceIndex, setValenceIndex] = useState(null);
  const [mode, setMode] = useState(loadStoredMode);
  // Both modes' values live in state at the same time and neither is ever
  // cleared on switch — only which one is displayed (and sent) changes —
  // so switching back and forth never loses what was already entered.
  const [quickArousal, setQuickArousal] = useState(QUICK_AROUSAL_DEFAULT);
  const [sliderValues, setSliderValues] = useState(initialSliderValues);
  const [amount, setAmount] = useState("");
  const [amountTouched, setAmountTouched] = useState(false);
  const [submitStatus, setSubmitStatus] = useState("idle"); // idle | loading | error
  // Same double-submit guard used across the app's other forms: a ref,
  // because React batches state updates, so two synchronous taps could
  // both still read "not submitted" before either update commits.
  const isSubmittingRef = useRef(false);

  const stage = STAGES[stageIndex];
  const canSubmitCheckin = category != null && valenceIndex != null;
  const amountNumber = Number(amount);
  const amountValid = amount.trim() !== "" && Number.isFinite(amountNumber) && amountNumber > 0;

  function handleModeChange(nextMode) {
    setMode(nextMode);
    storeMode(nextMode);
  }

  function checkinPayload() {
    const valence = VALENCE_LEVELS[valenceIndex];
    // Two families of fields in one payload, deliberately not merged into
    // one name each: category_code/valence are what the checkins table
    // needs; store_category/valence_z/perceived_*(or perceived_arousal)
    // are the field names the AI scoring pipeline expects. Same two
    // answers (category, valence) feed both; the arousal reading only
    // feeds one.
    //
    // checkin_mode tells the backend whether it's getting one combined
    // value (quick) or the four separate PDF sliders (detailed) — only
    // the active mode's fields are sent, not both, since the mode not
    // shown wasn't actually answered by the user this time.
    return {
      category_code: category,
      valence: valence.valence,

      store_category: category,
      valence_z: valence.valence_z,
      checkin_mode: mode,
      ...(mode === "quick" ? { perceived_arousal: quickArousal } : sliderValues),
    };
  }

  function handleCheckinSubmit(event) {
    event.preventDefault();
    if (isSubmittingRef.current) return;
    if (!canSubmitCheckin) return;
    isSubmittingRef.current = true;
    setStageIndex(1); // -> prediction
    isSubmittingRef.current = false;
  }

  function handleContinueToAmount() {
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
          currency: user?.currency ?? "LBP",
          category_code: category,
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

  const tier = overspendTier(MOCK_OVERSPEND_PROBABILITY);
  const percent = Math.round(MOCK_OVERSPEND_PROBABILITY * 100);

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
              <div className="checkin-mode-toggle" role="radiogroup" aria-label="How to report how you feel">
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

              {mode === "quick" ? (
                <div className="checkin__section--sliders">
                  <CheckinArousalSlider
                    id="slider-quick-arousal"
                    question={QUICK_AROUSAL_QUESTION}
                    value={quickArousal}
                    onChange={setQuickArousal}
                  />
                </div>
              ) : (
                <div className="checkin__section--sliders">
                  {SLIDERS.map((slider) => (
                    <CheckinSlider
                      key={slider.field}
                      id={`slider-${slider.field}`}
                      question={slider.question}
                      leftLabel={slider.leftLabel}
                      rightLabel={slider.rightLabel}
                      value={sliderValues[slider.field]}
                      onChange={(value) =>
                        setSliderValues((v) => ({ ...v, [slider.field]: value }))
                      }
                    />
                  ))}
                </div>
              )}
            </section>

            <button type="submit" className="btn btn--dark checkin__submit" disabled={!canSubmitCheckin}>
              Done
            </button>
          </form>
        )}

        {stage === "prediction" && (
          <section className="checkin__section">
            <div className={`prediction prediction--${tier}`}>
              <p className="prediction__label">Chance this runs past budget</p>
              <p className="prediction__value">{percent}%</p>
              <p className="prediction__context">{TIER_COPY[tier]}</p>
            </div>
            <button
              type="button"
              className="btn btn--dark checkin__submit"
              onClick={handleContinueToAmount}
            >
              Continue
            </button>
          </section>
        )}

        {stage === "amount" && (
          <form onSubmit={handleAmountSubmit} noValidate>
            <section className="checkin__section">
              <h2 className="checkin__question">How much is the purchase?</h2>
              <div className="field">
                <label htmlFor="checkin-amount" className="field__label">
                  Amount
                </label>
                <div className="checkin-amount__wrap">
                  <span className="checkin-amount__symbol" aria-hidden="true">
                    {currencySymbol(user?.currency)}
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
                    Enter an amount greater than {formatMoney(0, user?.currency)}
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

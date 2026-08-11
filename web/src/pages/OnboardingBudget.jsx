import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../lib/api";
import { currencySymbol } from "../lib/currency";
import "./Signup.css";
import "./Questionnaire.css";
import "./OnboardingBudget.css";

export default function OnboardingBudget() {
  const { user, refreshBudgetStatus } = useAuth();
  const navigate = useNavigate();

  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);
  const [submitStatus, setSubmitStatus] = useState("idle"); // idle | loading | error
  // Same double-submit guard as Signup/Login/Questionnaire: a ref, because
  // React batches setSubmitStatus, so two synchronous clicks could both
  // still read "not loading" before either update commits.
  const isSubmittingRef = useRef(false);

  const symbol = currencySymbol(user?.currency);
  const numericValue = Number(value);
  const isValid = value.trim() !== "" && Number.isFinite(numericValue) && numericValue > 0;
  const showError = touched && !isValid;

  async function submit() {
    if (isSubmittingRef.current) return;
    if (!isValid) {
      setTouched(true);
      return;
    }

    isSubmittingRef.current = true;
    setSubmitStatus("loading");

    try {
      const response = await apiFetch("/api/v1/onboarding/budget", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ monthly_budget: value }),
      });

      // 409 means it's already set — e.g. a second tab finished it first.
      // Either way the state the user wants (a budget on file) is now
      // true, so treat it the same as success.
      if (response.status === 201 || response.status === 409) {
        await refreshBudgetStatus();
        navigate("/home", { replace: true });
        return;
      }

      setSubmitStatus("error");
    } catch {
      setSubmitStatus("error");
    } finally {
      isSubmittingRef.current = false;
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    submit();
  }

  const isLoading = submitStatus === "loading";

  return (
    <div className="questionnaire">
      <a href="#budget-heading" className="skip-link">
        Skip to form
      </a>

      <div className="questionnaire__content">
        <form onSubmit={handleSubmit} noValidate>
          <h1 id="budget-heading" className="questionnaire__title">
            What&rsquo;s your monthly budget?
          </h1>
          <p className="questionnaire__intro">
            We&rsquo;ll flag days where your spending runs past it.
          </p>

          <div className="field">
            <label htmlFor="monthly-budget" className="field__label">
              Monthly budget
            </label>
            <div className="budget__input-wrap">
              <span className="budget__symbol" aria-hidden="true">
                {symbol}
              </span>
              <input
                id="monthly-budget"
                name="monthly_budget"
                type="number"
                inputMode="decimal"
                min="0"
                step="any"
                autoComplete="off"
                className={`field__control budget__input ${showError ? "field__control--error" : ""}`}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                onBlur={() => setTouched(true)}
                aria-invalid={showError ? "true" : undefined}
                aria-describedby={showError ? "monthly-budget-error" : undefined}
              />
            </div>
            {showError && (
              <p id="monthly-budget-error" className="field__error" role="alert">
                Enter an amount greater than {symbol}0
              </p>
            )}
          </div>

          {submitStatus === "error" && (
            <p className="questionnaire__form-error" role="alert">
              Couldn&rsquo;t reach the server. Nothing you entered was lost.{" "}
              <button type="button" className="questionnaire__retry" onClick={submit}>
                Try again
              </button>
            </p>
          )}

          <button
            type="submit"
            className="btn btn--primary questionnaire__submit"
            disabled={isLoading}
          >
            {isLoading ? "Saving…" : "Continue"}
          </button>
        </form>
      </div>
    </div>
  );
}

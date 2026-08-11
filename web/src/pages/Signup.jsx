import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Button from "../components/Button";
import { buildEcgPath } from "../components/landing/ecgPath";
import { useAuth } from "../context/AuthContext";
import SignupField from "./SignupField";
import { COUNTRIES } from "./signupCountries";
import "./Signup.css";

const ECG_PATH = buildEcgPath({ width: 320, height: 56, cycles: 2 });

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const STEP_1_FIELDS = ["fullName", "email", "password", "confirmPassword", "dateOfBirth"];

const INITIAL_VALUES = {
  fullName: "",
  email: "",
  password: "",
  confirmPassword: "",
  dateOfBirth: "",
  phone: "",
  address: "",
  city: "",
  country: "Lebanon",
};

const TODAY_ISO = new Date().toISOString().slice(0, 10);

function calculateAge(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  const dob = new Date(year, month - 1, day);
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const hasHadBirthdayThisYear =
    today.getMonth() > dob.getMonth() ||
    (today.getMonth() === dob.getMonth() && today.getDate() >= dob.getDate());
  if (!hasHadBirthdayThisYear) age -= 1;
  return age;
}

function validateField(name, values) {
  switch (name) {
    case "fullName":
      return values.fullName.trim() ? null : "Enter your full name";
    case "email":
      return EMAIL_RE.test(values.email.trim()) ? null : "Enter a valid email";
    case "password":
      return values.password.length >= 8 ? null : "Password must be at least 8 characters";
    case "confirmPassword":
      return values.confirmPassword === values.password ? null : "Passwords don't match";
    case "dateOfBirth":
      if (!values.dateOfBirth) return "Enter your date of birth";
      return calculateAge(values.dateOfBirth) >= 13 ? null : "You must be at least 13 years old";
    default:
      return null;
  }
}

export default function Signup() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [step, setStep] = useState(1);
  const [values, setValues] = useState(INITIAL_VALUES);
  const [touched, setTouched] = useState({});
  const [showPassword, setShowPassword] = useState(false);
  const [emailTaken, setEmailTaken] = useState(false);
  const [submitStatus, setSubmitStatus] = useState("idle"); // idle | loading | error
  const headingRef = useRef(null);
  // React batches setSubmitStatus, so two synchronous clicks (a real
  // double-click, or Enter + a click landing in the same tick) can both
  // read submitStatus as still "idle" before either update commits — the
  // state guard alone doesn't stop a true double-submit. A ref mutates
  // immediately, so the second call always sees what the first one just set.
  const isSubmittingRef = useRef(false);
  // Tracks the last step this effect actually acted on — see below.
  const lastFocusedStepRef = useRef(step);

  // Multi-step forms disorient screen reader users if focus is left behind
  // on a control that no longer exists — move it to the new step's heading,
  // same pattern as the landing page's skip-link target. Only on a real
  // step change, though: stealing focus to the heading on first load would
  // jump a keyboard user straight past the skip link and the logo link
  // before they ever get a chance to reach either. Comparing against the
  // last step this effect saw (rather than a simple "is this the first
  // call" flag) is what makes that safe under StrictMode, which
  // deliberately double-invokes effects on initial mount: a one-shot flag
  // gets consumed by the first invocation, so the second one would still
  // fire the focus-steal it was meant to prevent.
  useEffect(() => {
    if (lastFocusedStepRef.current === step) return;
    lastFocusedStepRef.current = step;
    headingRef.current?.focus();
  }, [step]);

  function handleChange(event) {
    const { name, value } = event.target;
    setValues((v) => ({ ...v, [name]: value }));
    if (name === "email") setEmailTaken(false);
  }

  function handleBlur(event) {
    const { name } = event.target;
    setTouched((t) => ({ ...t, [name]: true }));
  }

  function errorFor(name) {
    if (name === "email" && emailTaken) return "An account with this email already exists";
    if (!touched[name]) return null;
    return validateField(name, values);
  }

  const step1Errors = STEP_1_FIELDS.map((field) => validateField(field, values)).filter(Boolean);
  const canContinue = step1Errors.length === 0;

  function touchStep1Fields() {
    setTouched((t) => ({
      ...t,
      fullName: true,
      email: true,
      password: true,
      confirmPassword: true,
      dateOfBirth: true,
    }));
  }

  function handleContinue(event) {
    event.preventDefault();
    if (!canContinue) {
      touchStep1Fields();
      return;
    }
    setStep(2);
  }

  function handleBack() {
    setStep(1);
  }

  async function submit() {
    if (isSubmittingRef.current) return;
    if (!canContinue) {
      setStep(1);
      touchStep1Fields();
      return;
    }

    isSubmittingRef.current = true;
    setSubmitStatus("loading");

    try {
      // register() also logs the new account in (see AuthContext) — this
      // is what makes registration land the user signed in instead of at
      // a login form asking them to re-type what they just typed.
      await register({
        full_name: values.fullName.trim(),
        email: values.email.trim(),
        password: values.password,
        date_of_birth: values.dateOfBirth,
        phone: values.phone.trim() || null,
        address: values.address.trim() || null,
        city: values.city.trim() || null,
        country: values.country || null,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        currency: "LBP",
      });
      navigate("/questionnaire");
    } catch (error) {
      if (error.status === 409) {
        setEmailTaken(true);
        setStep(1);
        setSubmitStatus("idle");
        return;
      }
      setSubmitStatus("error");
    } finally {
      isSubmittingRef.current = false;
    }
  }

  function handleSubmitStep2(event) {
    event.preventDefault();
    submit();
  }

  const isLoading = submitStatus === "loading";

  return (
    <div className="signup">
      <a href="#signup-heading" className="skip-link">
        Skip to form
      </a>

      <div className="signup__form-side">
        <div className="signup__form-inner">
          <Link to="/" className="signup__home-link">
            &larr; Back to home
          </Link>

          <Link to="/" className="signup__logo">
            Financial&nbsp;Wellness
          </Link>

          <div className="signup__progress" role="group" aria-label="Signup progress">
            <span className={`signup__dot ${step === 1 ? "signup__dot--active" : ""}`} aria-hidden="true" />
            <span className={`signup__dot ${step === 2 ? "signup__dot--active" : ""}`} aria-hidden="true" />
            <span className="visually-hidden" aria-live="polite">
              Step {step} of 2
            </span>
          </div>

          {step === 1 ? (
            <form onSubmit={handleContinue} noValidate>
              <h1 id="signup-heading" className="signup__title" ref={headingRef} tabIndex={-1}>
                Create your account
              </h1>

              <SignupField
                label="Full name"
                name="fullName"
                value={values.fullName}
                onChange={handleChange}
                onBlur={handleBlur}
                error={errorFor("fullName")}
                autoComplete="name"
              />

              <SignupField
                label="Email"
                name="email"
                type="email"
                value={values.email}
                onChange={handleChange}
                onBlur={handleBlur}
                error={errorFor("email")}
                autoComplete="email"
              />

              <SignupField
                label="Password"
                name="password"
                type={showPassword ? "text" : "password"}
                value={values.password}
                onChange={handleChange}
                onBlur={handleBlur}
                error={errorFor("password")}
                autoComplete="new-password"
                suffix={
                  <button
                    type="button"
                    className="field__toggle"
                    onClick={() => setShowPassword((s) => !s)}
                    aria-pressed={showPassword}
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                }
              />

              <SignupField
                label="Confirm password"
                name="confirmPassword"
                type={showPassword ? "text" : "password"}
                value={values.confirmPassword}
                onChange={handleChange}
                onBlur={handleBlur}
                error={errorFor("confirmPassword")}
                autoComplete="new-password"
              />

              <SignupField
                label="Date of birth"
                name="dateOfBirth"
                type="date"
                value={values.dateOfBirth}
                onChange={handleChange}
                onBlur={handleBlur}
                error={errorFor("dateOfBirth")}
                max={TODAY_ISO}
              />

              <Button type="submit" variant="primary" disabled={!canContinue} className="signup__submit">
                Continue
              </Button>
            </form>
          ) : (
            <form onSubmit={handleSubmitStep2} noValidate>
              <button type="button" className="signup__back" onClick={handleBack} aria-label="Back to previous step">
                &larr; Back
              </button>

              <h1 id="signup-heading" className="signup__title" ref={headingRef} tabIndex={-1}>
                A few more details
              </h1>
              <p className="signup__subtitle">All optional — skip this if you&rsquo;d rather add it later.</p>

              <SignupField
                label="Phone"
                name="phone"
                type="tel"
                value={values.phone}
                onChange={handleChange}
                optional
                autoComplete="tel"
              />

              <SignupField
                label="Address"
                name="address"
                value={values.address}
                onChange={handleChange}
                optional
                autoComplete="street-address"
              />

              <SignupField
                label="City"
                name="city"
                value={values.city}
                onChange={handleChange}
                optional
                autoComplete="address-level2"
              />

              <SignupField
                label="Country"
                name="country"
                as="select"
                value={values.country}
                onChange={handleChange}
                optional
              >
                {COUNTRIES.map((country) => (
                  <option key={country} value={country}>
                    {country}
                  </option>
                ))}
              </SignupField>

              {submitStatus === "error" && (
                <p className="signup__form-error" role="alert">
                  Couldn&rsquo;t reach the server. Nothing you entered was lost.{" "}
                  <button type="button" className="signup__retry" onClick={submit}>
                    Try again
                  </button>
                </p>
              )}

              <div className="signup__actions">
                <Button type="submit" variant="primary" disabled={isLoading}>
                  {isLoading ? "Creating account…" : "Create account"}
                </Button>
                <Button type="button" variant="secondary" onClick={submit} disabled={isLoading}>
                  Skip for now
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>

      <aside className="signup__panel">
        <div className="signup__panel-inner">
          <p className="signup__panel-eyebrow">What happens next</p>
          <p className="signup__panel-copy">
            You&rsquo;re almost there — log in next, then a couple of quick questions to set your
            baseline.
          </p>
          <div className="signup__ecg" aria-hidden="true">
            <svg viewBox="0 0 320 56" preserveAspectRatio="none" className="signup__ecg-svg">
              <path d={ECG_PATH} pathLength="1" className="signup__ecg-path" />
            </svg>
          </div>
        </div>
      </aside>
    </div>
  );
}

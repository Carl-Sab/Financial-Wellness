import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Button from "../components/Button";
import { useAuth } from "../context/AuthContext";
import { buildEcgPath } from "../components/landing/ecgPath";
import SignupField from "./SignupField";
import "./Signup.css";
import "./Login.css";

const ECG_PATH = buildEcgPath({ width: 320, height: 56, cycles: 2 });

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateField(name, values) {
  switch (name) {
    case "email":
      return EMAIL_RE.test(values.email.trim()) ? null : "Enter a valid email";
    case "password":
      return values.password ? null : "Enter your password";
    default:
      return null;
  }
}

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [values, setValues] = useState({ email: "", password: "" });
  const [touched, setTouched] = useState({});
  const [showPassword, setShowPassword] = useState(false);
  const [submitStatus, setSubmitStatus] = useState("idle"); // idle | loading
  const [formError, setFormError] = useState(null);
  // Same pattern as Signup: a ref, not a state flag — two synchronous
  // clicks would both read a stale "not loading" state before either
  // setSubmitStatus("loading") call commits, so the guard has to be
  // something that mutates immediately.
  const isSubmittingRef = useRef(false);

  function handleChange(event) {
    const { name, value } = event.target;
    setValues((v) => ({ ...v, [name]: value }));
    if (formError) setFormError(null);
  }

  function handleBlur(event) {
    const { name } = event.target;
    setTouched((t) => ({ ...t, [name]: true }));
  }

  function errorFor(name) {
    if (!touched[name]) return null;
    return validateField(name, values);
  }

  const fieldErrors = ["email", "password"].map((f) => validateField(f, values)).filter(Boolean);
  const canSubmit = fieldErrors.length === 0;

  async function handleSubmit(event) {
    event.preventDefault();
    if (isSubmittingRef.current) return;
    if (!canSubmit) {
      setTouched({ email: true, password: true });
      return;
    }

    isSubmittingRef.current = true;
    setSubmitStatus("loading");
    setFormError(null);

    try {
      const questionnaireComplete = await login(values.email.trim(), values.password);
      navigate(questionnaireComplete ? "/home" : "/questionnaire", { replace: true });
    } catch (error) {
      if (error.status === 401) {
        setFormError("Email or password is incorrect");
      } else if (error.status === 429) {
        setFormError("Too many attempts. Try again in a few minutes.");
      } else {
        setFormError("Couldn't reach the server. Try again.");
      }
      setSubmitStatus("idle");
    } finally {
      isSubmittingRef.current = false;
    }
  }

  const isLoading = submitStatus === "loading";

  return (
    <div className="signup">
      <a href="#login-heading" className="skip-link">
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

          <form onSubmit={handleSubmit} noValidate>
            <h1 id="login-heading" className="signup__title">
              Log in
            </h1>

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
              autoComplete="current-password"
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

            {formError && (
              <p className="signup__form-error" role="alert">
                {formError}
              </p>
            )}

            <Button type="submit" variant="primary" disabled={isLoading} className="signup__submit">
              {isLoading ? "Logging in…" : "Log in"}
            </Button>

            <p className="login__signup-prompt">
              Don&rsquo;t have an account? <Link to="/signup">Sign up</Link>
            </p>
          </form>
        </div>
      </div>

      <aside className="signup__panel">
        <div className="signup__panel-inner">
          <p className="signup__panel-eyebrow">Welcome back</p>
          <p className="signup__panel-copy">
            Check in before your next purchase and see how it compares to your baseline.
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

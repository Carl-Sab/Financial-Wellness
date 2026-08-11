import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, refreshOnce, setAccessToken as setApiAccessToken, setOnAuthFailure } from "../lib/api";

const AuthContext = createContext(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}

async function fetchMe(token) {
  const response = await fetch("/api/v1/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
    credentials: "include",
  });
  if (!response.ok) return null;
  return response.json();
}

// Three states, not two: null means "haven't checked yet" (or logged out),
// distinct from false ("checked, not done"). RequireQuestionnaire and
// Questionnaire.jsx both need to tell "still loading" apart from "actually
// incomplete" so they don't flash the wrong screen before the check lands.
async function fetchQuestionnaireComplete() {
  const response = await apiFetch("/api/v1/questionnaire/me");
  if (response.status === 200) return true;
  if (response.status === 404) return false;
  return null;
}

// Same three-state shape as fetchQuestionnaireComplete, for RequireBudget
// and OnboardingBudget.jsx.
async function fetchBudgetComplete() {
  const response = await apiFetch("/api/v1/onboarding/budget/me");
  if (response.status === 200) return true;
  if (response.status === 404) return false;
  return null;
}

export function AuthProvider({ children }) {
  const [accessToken, setAccessTokenState] = useState(null);
  const [user, setUser] = useState(null);
  const [questionnaireComplete, setQuestionnaireComplete] = useState(null);
  const [budgetComplete, setBudgetComplete] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // The single place a token is adopted: updates React state (for
  // rendering — the header needs to know it's logged in) AND api.js's
  // module state, synchronously, in that order doesn't matter but both
  // must happen before this function returns. A useEffect watching
  // accessToken would also work for keeping api.js in sync eventually, but
  // "eventually" is the problem — effects run after the current call stack
  // unwinds, so a fetchMe() call made right after this would still read
  // api.js's *previous* token and attach the wrong Authorization header.
  const applySession = useCallback(async (token) => {
    setApiAccessToken(token);
    setAccessTokenState(token);
    const me = token ? await fetchMe(token) : null;
    setUser(me);
    if (!me) {
      setApiAccessToken(null);
      setAccessTokenState(null);
      setQuestionnaireComplete(null);
      setBudgetComplete(null);
      return { user: null, questionnaireComplete: null, budgetComplete: null };
    }
    const [complete, budget] = await Promise.all([
      fetchQuestionnaireComplete(),
      fetchBudgetComplete(),
    ]);
    setQuestionnaireComplete(complete);
    setBudgetComplete(budget);
    return { user: me, questionnaireComplete: complete, budgetComplete: budget };
  }, []);

  const clearAuth = useCallback(() => {
    setApiAccessToken(null);
    setAccessTokenState(null);
    setUser(null);
    setQuestionnaireComplete(null);
    setBudgetComplete(null);
  }, []);

  // Exposed so Questionnaire.jsx can re-check right after a successful
  // submit — cheaper than re-running the whole applySession/fetchMe dance
  // just to pick up one new fact.
  const refreshQuestionnaireStatus = useCallback(async () => {
    const complete = await fetchQuestionnaireComplete();
    setQuestionnaireComplete(complete);
    return complete;
  }, []);

  // Same idea, for OnboardingBudget.jsx after a successful submit.
  const refreshBudgetStatus = useCallback(async () => {
    const budget = await fetchBudgetComplete();
    setBudgetComplete(budget);
    return budget;
  }, []);

  // Registered once: api.js calls this when a retry-after-refresh still
  // fails, meaning the session is unrecoverable — clear state and send the
  // user back to login.
  useEffect(() => {
    setOnAuthFailure(() => {
      clearAuth();
      navigate("/login");
    });
  }, [clearAuth, navigate]);

  // Runs once on mount: an in-memory access token doesn't survive a page
  // reload by definition, but the httpOnly refresh cookie does, so this is
  // what actually restores a session after F5 rather than bouncing a
  // logged-in user to the login page. Goes through refreshOnce() (the same
  // guarded call apiFetch uses), not a bare refresh call — React StrictMode
  // deliberately double-invokes mount effects in dev, and without the
  // shared guard that would fire two real /auth/refresh requests, rotating
  // the refresh cookie twice for one page load.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await refreshOnce();
      if (cancelled) return;
      if (token) {
        await applySession(token);
      }
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(
    async (email, password) => {
      const response = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        throw Object.assign(new Error("Login failed"), { status: response.status });
      }
      const { access_token: token } = await response.json();
      const { questionnaireComplete: complete } = await applySession(token);
      return complete;
    },
    [applySession],
  );

  const register = useCallback(
    async (payload) => {
      const response = await fetch("/api/v1/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.status !== 201) {
        throw Object.assign(new Error("Registration failed"), { status: response.status });
      }
      // Auto-login: the account exists now, so sign the new user straight
      // in rather than sending them to a login form to re-type what they
      // just typed.
      await login(payload.email, payload.password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" }).catch(() => {});
    clearAuth();
  }, [clearAuth]);

  const value = {
    user,
    accessToken,
    loading,
    questionnaireComplete,
    refreshQuestionnaireStatus,
    budgetComplete,
    refreshBudgetStatus,
    login,
    logout,
    register,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

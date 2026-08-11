/**
 * Fetch wrapper for authenticated API calls. Not for the auth endpoints
 * themselves (login/register/refresh/logout) — a 401 from /auth/login means
 * "wrong password", not "your session expired, try refreshing", so those
 * calls go through plain fetch() directly in AuthContext instead. This
 * wrapper is for everything else: attach the access token, and if the
 * server says it's stale, refresh once and retry transparently.
 *
 * The access token itself lives here as module state, not in a React
 * context read at call time — this file has to be usable from plain
 * functions with no component tree above them. AuthContext is what keeps
 * this in sync: it calls setAccessToken() the instant it obtains a new
 * token (synchronously, not via a useEffect — see the comment there about
 * why the effect alone isn't fast enough), and this module never mutates
 * React state directly, only calls the onAuthFailure callback AuthContext
 * registers on mount.
 */

let accessToken = null;
let onAuthFailure = null;
let refreshPromise = null;

export function setAccessToken(token) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export function setOnAuthFailure(callback) {
  onAuthFailure = callback;
}

/**
 * POST /auth/refresh using the httpOnly cookie. On success, updates the
 * module's access token and returns it; on failure, clears it and returns
 * null. Deliberately doesn't call onAuthFailure itself — this is also used
 * for the initial "restore a session on page load" attempt, where a 401 is
 * an entirely expected, silent "no session" rather than a failure to react
 * to.
 */
export async function refreshAccessToken() {
  let response;
  try {
    response = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
    });
  } catch {
    setAccessToken(null);
    return null;
  }

  if (!response.ok) {
    setAccessToken(null);
    return null;
  }

  const body = await response.json();
  setAccessToken(body.access_token);
  return body.access_token;
}

// Several callers can want a refresh at once — a page firing off a handful
// of calls right as the access token expires, apiFetch's own 401 handling
// racing against AuthContext's on-mount session restore, or (in dev only)
// React StrictMode invoking that mount effect twice. Without this, each
// caller would independently kick off its own /auth/refresh, rotating the
// refresh cookie multiple times and racing each other. Every refresh
// call-site in this app — apiFetch below and AuthContext's mount effect —
// goes through this, so there is exactly one source of "a refresh is
// happening right now" regardless of who asked for it.
export function refreshOnce() {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/**
 * fetch() with the access token attached and one automatic retry-after-
 * refresh on a 401. Returns the raw Response either way (matching plain
 * fetch's contract) — callers still check response.status themselves for
 * everything that isn't "my session died", same as before this wrapper
 * existed.
 */
export async function apiFetch(path, options = {}) {
  const doFetch = (token) => {
    const headers = new Headers(options.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(path, { ...options, headers, credentials: "include" });
  };

  let response = await doFetch(accessToken);

  if (response.status === 401) {
    const newToken = await refreshOnce();
    if (!newToken) {
      onAuthFailure?.();
      return response;
    }

    response = await doFetch(newToken);
    if (response.status === 401) {
      // Refresh reported success but the server still won't take the
      // resulting token — treat the session as unrecoverable rather than
      // retry indefinitely.
      onAuthFailure?.();
    }
  }

  return response;
}

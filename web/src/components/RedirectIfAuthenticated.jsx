import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Wraps /login and /signup: an already-authenticated user hitting either
 * gets sent to /home instead of seeing a form for a session they already
 * have. Logged-out visitors pass through untouched.
 */
export default function RedirectIfAuthenticated({ children }) {
  const { user, loading } = useAuth();

  // Still resolving the on-mount session check — render nothing rather
  // than flash the login/signup form before a real session is found.
  if (loading) return null;

  if (user) {
    return <Navigate to="/home" replace />;
  }

  return children;
}

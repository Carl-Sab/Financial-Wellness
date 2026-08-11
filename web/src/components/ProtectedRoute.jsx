import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Not wrapped around any route yet — available for when there's a real
 * protected page to gate. Usage: <Route path="/x" element={<ProtectedRoute><X /></ProtectedRoute>} />.
 */
export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Still resolving the on-mount refresh — render nothing rather than
  // redirect, or a page reload for an already-logged-in user would flash
  // the login page before snapping back.
  if (loading) return null;

  if (!user) {
    // location is handed to /login via state.from, so it can send the user
    // back to whatever they were trying to reach once they're signed in.
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

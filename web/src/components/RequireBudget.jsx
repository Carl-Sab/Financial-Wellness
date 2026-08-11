import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Wraps /home and future app pages, alongside RequireQuestionnaire — never
 * /onboarding/budget itself (that would be a redirect loop). Expects to
 * sit inside ProtectedRoute (and typically inside RequireQuestionnaire, so
 * the questionnaire check runs first): both have already guaranteed `user`
 * is set by the time this renders.
 */
export default function RequireBudget({ children }) {
  const { loading, budgetComplete } = useAuth();

  // Still resolving the on-mount session/budget check — render nothing
  // rather than redirect, or a logged-in user would flash through an
  // incorrect redirect before the real state lands.
  if (loading) return null;

  if (budgetComplete === false) {
    return <Navigate to="/onboarding/budget" replace />;
  }

  return children;
}

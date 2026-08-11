import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Wraps /home and future app pages — never /, /login, /signup, or
 * /questionnaire itself (that last one would be a redirect loop). Expects
 * to sit inside ProtectedRoute, which has already guaranteed `user` is set
 * by the time this renders; this component only adds the questionnaire
 * check on top of that.
 */
export default function RequireQuestionnaire({ children }) {
  const { loading, questionnaireComplete } = useAuth();

  // Still resolving the on-mount session/questionnaire check — render
  // nothing rather than redirect, or a logged-in user would flash through
  // an incorrect redirect before the real state lands.
  if (loading) return null;

  if (questionnaireComplete === false) {
    return <Navigate to="/questionnaire" replace />;
  }

  return children;
}

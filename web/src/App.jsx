import { Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import RedirectIfAuthenticated from "./components/RedirectIfAuthenticated";
import RequireBudget from "./components/RequireBudget";
import RequireQuestionnaire from "./components/RequireQuestionnaire";
import Home from "./pages/Home";
import LandingPage from "./pages/LandingPage";
import Login from "./pages/Login";
import OnboardingBudget from "./pages/OnboardingBudget";
import Questionnaire from "./pages/Questionnaire";
import Signup from "./pages/Signup";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/login"
        element={
          <RedirectIfAuthenticated>
            <Login />
          </RedirectIfAuthenticated>
        }
      />
      <Route
        path="/signup"
        element={
          <RedirectIfAuthenticated>
            <Signup />
          </RedirectIfAuthenticated>
        }
      />
      <Route
        path="/questionnaire"
        element={
          <ProtectedRoute>
            <Questionnaire />
          </ProtectedRoute>
        }
      />
      <Route
        path="/onboarding/budget"
        element={
          <ProtectedRoute>
            <OnboardingBudget />
          </ProtectedRoute>
        }
      />
      <Route
        path="/home"
        element={
          <ProtectedRoute>
            <RequireQuestionnaire>
              <RequireBudget>
                <Home />
              </RequireBudget>
            </RequireQuestionnaire>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ArduinoProvider } from "./context/ArduinoContext.jsx";
import { AuthProvider } from "./context/AuthContext.jsx";
import "./index.css";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <ArduinoProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ArduinoProvider>
    </BrowserRouter>
  </StrictMode>,
);

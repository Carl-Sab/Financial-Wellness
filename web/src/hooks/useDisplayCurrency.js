import { useState } from "react";

// A view-only preference (not account/budget currency) — how amounts already
// returned by the API get displayed. Persisted the same way Checkin's
// quick/detailed mode is: plain localStorage, no backend round trip.
const STORAGE_KEY = "display.currency";

function loadStored() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "USD" ? "USD" : "LBP"; // LBP is the default
  } catch {
    return "LBP"; // localStorage can throw (private browsing, quota)
  }
}

function storeValue(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    // Non-fatal — the choice just won't persist this time.
  }
}

export function useDisplayCurrency() {
  const [displayCurrency, setDisplayCurrencyState] = useState(loadStored);

  function setDisplayCurrency(value) {
    setDisplayCurrencyState(value);
    storeValue(value);
  }

  return [displayCurrency, setDisplayCurrency];
}

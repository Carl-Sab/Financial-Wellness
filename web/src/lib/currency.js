const SYMBOLS = {
  LBP: "L.L.",
  USD: "$",
  EUR: "€",
  GBP: "£",
};

export function currencySymbol(code) {
  if (!code) return "";
  return SYMBOLS[code] ?? `${code} `;
}

// Amounts arrive from the API as decimal strings (e.g. "1650000.00") —
// Number() is safe here since these are display-only, never re-submitted.
export function formatMoney(amount, currencyCode) {
  const value = Number(amount);
  const formatted = value.toLocaleString("en-US", {
    minimumFractionDigits: value % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  });
  return `${currencySymbol(currencyCode)}${formatted}`;
}

// Fixed display-only rate, matching the backend's
// wellness.services.currency.USD_TO_LBP exactly — used for the LBP/$
// view toggle, never for anything submitted back to the server.
export const USD_TO_LBP = 90000;

export function convertAmount(amount, fromCurrency, toCurrency) {
  const value = Number(amount);
  if (fromCurrency === toCurrency) return value;
  if (fromCurrency === "USD" && toCurrency === "LBP") return value * USD_TO_LBP;
  if (fromCurrency === "LBP" && toCurrency === "USD") return value / USD_TO_LBP;
  // Unsupported pair (e.g. EUR/GBP) — display unconverted rather than throw.
  return value;
}

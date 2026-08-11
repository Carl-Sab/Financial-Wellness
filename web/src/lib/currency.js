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

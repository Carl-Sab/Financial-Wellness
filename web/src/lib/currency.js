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

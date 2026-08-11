"""Fixed-rate LBP/USD conversion — the only two currencies user_goals.currency
accepts. transactions.currency/users.currency stay freeform Text columns (a
stray "EUR"/"GBP" row is left unconverted by callers, same as before this
module existed), but every amount actually folded into a spending-summary
window is expected to be one of SUPPORTED_CURRENCIES.
"""

from decimal import ROUND_HALF_UP, Decimal

USD_TO_LBP = Decimal("90000")
SUPPORTED_CURRENCIES = {"LBP", "USD"}

_CENTS = Decimal("0.01")


def convert(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    if from_currency == to_currency:
        return amount
    if from_currency == "USD" and to_currency == "LBP":
        result = amount * USD_TO_LBP
    elif from_currency == "LBP" and to_currency == "USD":
        result = amount / USD_TO_LBP
    else:
        raise ValueError(f"Unsupported currency conversion: {from_currency} -> {to_currency}")
    return quantize(result)


def quantize(amount: Decimal) -> Decimal:
    return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)

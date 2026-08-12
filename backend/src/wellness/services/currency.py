"""Fixed-rate LBP/USD conversion — the only two currencies user_goals.currency
accepts. transactions.currency/users.currency stay freeform Text columns (a
stray "EUR"/"GBP" row is left unconverted by callers, same as before this
module existed), but every amount actually folded into a spending-summary
window is expected to be one of SUPPORTED_CURRENCIES.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import case
from sqlalchemy.sql.elements import ColumnElement

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


def converted_amount_expr(
    amount_col: ColumnElement[Any], currency_col: ColumnElement[Any], display_currency: str
) -> ColumnElement[Any]:
    """SQL expression converting each row's amount_col from its own
    currency_col value into display_currency, at the fixed LBP/USD rate —
    for queries that sum/aggregate amounts that may span both currencies
    (e.g. spending.py's window totals, analysis.py's mood buckets). Any
    other stored currency value falls through unconverted: currency_col is
    typically a freeform Text column, not restricted to SUPPORTED_CURRENCIES.
    """
    if display_currency == "USD":
        return case(
            (currency_col == "LBP", amount_col / USD_TO_LBP),
            else_=amount_col,
        )
    if display_currency == "LBP":
        return case(
            (currency_col == "USD", amount_col * USD_TO_LBP),
            else_=amount_col,
        )
    return amount_col

"""Deterministic cash-account position sizing for MomoPro AI."""

from __future__ import annotations

import math
from typing import Any, Dict, Optional


def calculate_position_size(
    account_size: float,
    risk_percent: float,
    entry_price: float,
    stop_price: float,
) -> Dict[str, Any]:
    """Calculate a whole-share position using both risk and cash constraints.

    The final position can never cost more than account_size and can never
    exceed the selected dollar-risk budget at the supplied stop.
    """
    account = max(float(account_size or 0.0), 0.0)
    risk_pct = min(max(float(risk_percent or 0.0), 0.0), 100.0)
    entry = max(float(entry_price or 0.0), 0.0)
    stop = max(float(stop_price or 0.0), 0.0)

    risk_budget = account * (risk_pct / 100.0)
    risk_per_share: Optional[float] = None
    error: Optional[str] = None

    if entry <= 0:
        error = "Enter a valid entry price greater than $0."
    elif stop <= 0:
        error = "Enter a valid stop price greater than $0."
    elif stop >= entry:
        error = "For a long trade, the stop must be below the entry price."
    else:
        risk_per_share = entry - stop

    cash_based_shares = math.floor(account / entry) if account > 0 and entry > 0 else 0
    risk_based_shares = (
        math.floor(risk_budget / risk_per_share)
        if risk_budget > 0 and risk_per_share and risk_per_share > 0
        else 0
    )

    final_shares = min(cash_based_shares, risk_based_shares) if not error else 0
    position_value = final_shares * entry
    total_dollar_risk = (
        final_shares * risk_per_share if risk_per_share is not None else 0.0
    )
    unused_cash = max(account - position_value, 0.0)
    unused_risk_budget = max(risk_budget - total_dollar_risk, 0.0)

    if final_shares <= 0:
        constraint = "Unavailable"
    elif cash_based_shares < risk_based_shares:
        constraint = "Cash-Limited"
    elif risk_based_shares < cash_based_shares:
        constraint = "Risk-Limited"
    else:
        constraint = "Cash and Risk Limits Match"

    # Hard safety invariant: position value may never exceed cash account size.
    if position_value > account + 1e-9:
        raise AssertionError("Position value exceeded account size.")

    return {
        "account_size": account,
        "risk_percent": risk_pct,
        "risk_budget": risk_budget,
        "entry_price": entry,
        "stop_price": stop,
        "risk_per_share": risk_per_share,
        "risk_based_shares": risk_based_shares,
        "cash_based_shares": cash_based_shares,
        "final_shares": final_shares,
        "position_value": position_value,
        "total_dollar_risk": total_dollar_risk,
        "unused_cash": unused_cash,
        "unused_risk_budget": unused_risk_budget,
        "sizing_constraint": constraint,
        "error": error,
    }

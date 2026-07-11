from __future__ import annotations
from typing import Any


def calculate_exit_warnings(stock: Any, trend: dict, timeframes: dict, pattern: dict) -> dict:
    def num(key):
        try:
            x = stock.get(key)
            return float(x) if x is not None else None
        except Exception:
            return None
    warnings = []
    actions = []
    rvol = num("RVOL")
    distance = num("Distance EMA21 %")
    t1r = num("T1 R")
    if rvol is not None and rvol < 0.7:
        warnings.append("Participation is weak; breakouts may fail more easily.")
    if distance is not None and distance > 6:
        warnings.append("Price is extended from EMA21; protect against mean reversion.")
    if t1r is not None and t1r < 1:
        warnings.append("Nearest target offers less than 1R.")
    if trend.get("score") is not None and trend["score"] < 55:
        warnings.append("Overall trend health is mixed or weak.")
    if timeframes.get("alignment") in {"Mixed", "Conflict"}:
        warnings.append("Lower and higher timeframes are not fully aligned.")
    if pattern.get("maturity") in {"Late Stage", "Triggered"}:
        actions.append("Avoid chasing; wait for a controlled retest or confirmation hold.")
    actions.extend([
        "Consider partial profits into T1 if momentum weakens.",
        "Tighten risk after a decisive loss of EMA21 or the selected support zone.",
        "Reassess before earnings or a major scheduled catalyst.",
    ])
    severity = "High" if len(warnings) >= 4 else "Moderate" if len(warnings) >= 2 else "Low"
    return {"severity": severity, "warnings": warnings, "management_actions": actions}

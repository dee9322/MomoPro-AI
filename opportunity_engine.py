from __future__ import annotations

from typing import Any, Dict, Tuple


def _number(row: Dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = row.get(name)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            pass
    return None


def calculate_opportunity_score(row: Dict[str, Any]) -> Tuple[int, str, Dict[str, int]]:
    """Scores how attractive the current entry is for Dee's EMA21 swing style."""
    score = 50
    parts = {"location": 0, "setup": 0, "momentum": 0, "liquidity": 0, "risk": 0}

    price = _number(row, "Price", "price", "Close")
    ema21 = _number(row, "EMA21", "EMA 21", "ema21")
    rvol = _number(row, "RVOL", "Relative Volume")
    atr = _number(row, "ATR %", "ATR%", "atr_pct")
    momo = _number(row, "Momo Score", "MomoScore")
    confidence = _number(row, "Confidence %", "Confidence", "AI Confidence")
    rr = _number(row, "Risk Reward", "Risk/Reward", "R:R")
    setup = str(row.get("Setup") or row.get("setup") or "").lower()
    grade = str(row.get("Grade") or "").upper()

    if price and ema21 and ema21 > 0:
        distance = (price - ema21) / ema21 * 100
        if -1.5 <= distance <= 3.0:
            parts["location"] = 24
        elif -3.0 <= distance < -1.5 or 3.0 < distance <= 6.0:
            parts["location"] = 12
        elif distance > 10:
            parts["location"] = -28
        elif distance > 6:
            parts["location"] = -14
        else:
            parts["location"] = -6

    if any(token in setup for token in ("reclaim", "retest", "continuation", "flag")):
        parts["setup"] += 15
    if "fresh" in setup:
        parts["setup"] += 5
    if grade.startswith("A"):
        parts["setup"] += 8
    elif grade.startswith("B"):
        parts["setup"] += 3

    if momo is not None:
        parts["momentum"] += 10 if momo >= 80 else 6 if momo >= 70 else 0 if momo >= 55 else -6
    if confidence is not None:
        parts["momentum"] += 6 if confidence >= 80 else 3 if confidence >= 65 else -3

    if rvol is not None:
        parts["liquidity"] += 7 if rvol >= 1.5 else 4 if rvol >= 1.1 else -4
    if atr is not None:
        parts["liquidity"] += 5 if 4 <= atr <= 15 else 1 if atr > 0 else 0

    if rr is not None:
        parts["risk"] += 8 if rr >= 2 else 3 if rr >= 1.5 else -8 if rr < 1 else 0

    score += sum(parts.values())
    score = max(0, min(100, round(score)))
    if score >= 85:
        reason = "High-priority entry location for your EMA21 swing strategy."
    elif score >= 70:
        reason = "Attractive setup, but confirm price action and risk before entry."
    elif score >= 50:
        reason = "Developing opportunity; it is not fully aligned yet."
    elif price and ema21 and price > ema21 * 1.06:
        reason = "Quality may be strong, but price is extended from EMA21."
    else:
        reason = "Current entry is not well aligned with your preferred setup."
    return score, reason, parts

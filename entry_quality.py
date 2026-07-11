from __future__ import annotations
from typing import Any


def calculate_entry_quality(stock: Any, pattern: dict, trend: dict, timeframes: dict) -> dict:
    def num(key, default=None):
        try:
            value = stock.get(key)
            return float(value) if value is not None else default
        except Exception:
            return default

    distance = num("Distance EMA21 %")
    rvol = num("RVOL", 0)
    rr = num("Risk Reward")
    t1r = num("T1 R")
    score = 0
    reasons = []
    warnings = []

    if distance is not None:
        if 0 <= distance <= 2: score += 25; reasons.append("Ideal EMA21 location")
        elif 2 < distance <= 4: score += 18; reasons.append("Workable EMA21 location")
        elif 4 < distance <= 6: score += 8; warnings.append("Slightly extended")
        else: warnings.append("Poor EMA21 entry location")
    if rvol >= 1.5: score += 18; reasons.append("Strong volume confirmation")
    elif rvol >= 1.0: score += 12; reasons.append("Acceptable participation")
    else: warnings.append("Volume confirmation is weak")
    if rr is not None:
        if rr >= 2: score += 22; reasons.append("Favorable structural risk/reward")
        elif rr >= 1.5: score += 15
        else: warnings.append("Risk/reward is limited")
    if t1r is not None and t1r >= 1: score += 8
    score += round((pattern.get("pattern_score") or 0) * 0.15)
    score += round((trend.get("score") or 0) * 0.07)
    score += round((timeframes.get("alignment_score") or 0) * 0.05)
    score = max(0, min(score, 100))
    grade = "A+" if score >= 90 else "A" if score >= 80 else "B" if score >= 70 else "C" if score >= 60 else "Wait"
    status = "Excellent" if score >= 85 else "Good" if score >= 72 else "Developing" if score >= 60 else "Poor"
    return {"score": score, "grade": grade, "status": status, "reasons": reasons, "warnings": warnings}

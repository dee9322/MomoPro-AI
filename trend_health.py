from __future__ import annotations

from typing import Any
import pandas as pd


def calculate_trend_health(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or len(df) < 60:
        return {"score": None, "rating": "Unavailable", "strengths": [], "warnings": []}

    latest = df.iloc[-1]
    prev20 = df.iloc[-21]
    close = float(latest["close"])
    ema21 = float(latest["ema21"])
    ema50 = float(latest["ema50"])
    ema200 = float(latest["ema200"])
    score = 0
    strengths = []
    warnings = []

    if close > ema21:
        score += 18; strengths.append("Price is above EMA21")
    else:
        warnings.append("Price is below EMA21")
    if ema21 > ema50:
        score += 18; strengths.append("EMA21 is above EMA50")
    else:
        warnings.append("EMA21 is below EMA50")
    if ema50 > ema200:
        score += 18; strengths.append("EMA50 is above EMA200")
    else:
        warnings.append("Long-term EMA structure is not fully aligned")
    if close > ema200:
        score += 12; strengths.append("Price is above EMA200")
    if float(latest["ema21"]) > float(prev20["ema21"]):
        score += 12; strengths.append("EMA21 slope is rising")
    if float(latest["ema50"]) > float(prev20["ema50"]):
        score += 10; strengths.append("EMA50 slope is rising")

    last20 = df.tail(20)
    first_low = float(last20["low"].iloc[:10].min())
    second_low = float(last20["low"].iloc[10:].min())
    if second_low > first_low:
        score += 12; strengths.append("Recent structure contains a higher low")
    else:
        warnings.append("Recent higher-low structure is not confirmed")

    score = max(0, min(round(score), 100))
    rating = "Excellent" if score >= 85 else "Healthy" if score >= 70 else "Mixed" if score >= 50 else "Weak"
    return {"score": score, "rating": rating, "strengths": strengths, "warnings": warnings}

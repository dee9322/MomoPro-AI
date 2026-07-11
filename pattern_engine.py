from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def _valid(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def detect_patterns(df: pd.DataFrame) -> dict[str, Any]:
    """Deterministic swing-pattern recognition from OHLCV history."""
    if df is None or len(df) < 60:
        return {
            "primary_pattern": "Insufficient Data",
            "pattern_score": None,
            "patterns": [],
            "maturity": "Unavailable",
            "failure_conditions": [],
        }

    data = df.copy().reset_index(drop=True)
    latest = data.iloc[-1]
    prev = data.iloc[-2]
    close = float(latest["close"])
    ema21 = float(latest["ema21"])
    ema50 = float(latest["ema50"])
    atr = float(latest["atr14"]) if _valid(latest.get("atr14")) else close * 0.04
    rvol = float(latest.get("rvol", 1.0)) if _valid(latest.get("rvol")) else 1.0

    patterns: list[dict[str, Any]] = []

    # EMA21 reclaim
    if float(prev["close"]) <= float(prev["ema21"]) and close > ema21:
        score = 78 + min(12, max(0, (rvol - 1) * 10))
        patterns.append({"name": "EMA21 Reclaim", "score": round(score), "maturity": "Fresh"})

    # EMA21 retest / pullback
    recent = data.tail(5)
    touched = bool((recent["low"] <= recent["ema21"] * 1.01).any())
    held = close >= ema21 and float(recent["close"].min()) >= float(recent["ema50"].min())
    if touched and held:
        distance = abs(close - ema21) / ema21 * 100
        score = max(55, 90 - distance * 8)
        patterns.append({"name": "EMA21 Retest", "score": round(score), "maturity": "Developing"})

    # Higher-low continuation
    lows = data["low"].tail(25)
    first_low = float(lows.iloc[:12].min())
    second_low = float(lows.iloc[12:].min())
    if second_low > first_low and close > ema21 > ema50:
        patterns.append({"name": "Higher-Low Continuation", "score": 76, "maturity": "Confirmed"})

    # Tight consolidation / bull flag proxy
    last10 = data.tail(10)
    prior10 = data.iloc[-20:-10]
    recent_range = (float(last10["high"].max()) - float(last10["low"].min())) / close * 100
    prior_move = (float(prior10["close"].iloc[-1]) - float(prior10["close"].iloc[0])) / float(prior10["close"].iloc[0]) * 100
    volume_contract = float(last10["volume"].mean()) < float(prior10["volume"].mean())
    if prior_move >= 5 and recent_range <= max(8, (atr / close * 100) * 2.2) and volume_contract:
        patterns.append({"name": "Bull Flag / Tight Consolidation", "score": 82, "maturity": "Developing"})

    # Ascending triangle proxy: flat highs, rising lows
    highs = data["high"].tail(20)
    lows20 = data["low"].tail(20)
    high_dispersion = float(highs.std()) / close * 100
    first_half_low = float(lows20.iloc[:10].min())
    second_half_low = float(lows20.iloc[10:].min())
    if high_dispersion <= 2.0 and second_half_low > first_half_low * 1.01:
        patterns.append({"name": "Ascending Triangle", "score": 79, "maturity": "Near Breakout"})

    # Breakout base
    prior_high = float(data["high"].iloc[-21:-1].max())
    if close > prior_high and rvol >= 1.2:
        score = min(96, 80 + (rvol - 1.2) * 10)
        patterns.append({"name": "Above-Average-Volume Breakout", "score": round(score), "maturity": "Triggered"})

    # Cup-like rounded recovery proxy
    last60 = data.tail(60)
    left = float(last60["high"].iloc[:15].max())
    middle = float(last60["low"].iloc[20:40].min())
    right = float(last60["high"].iloc[-15:].max())
    rim_similarity = abs(left - right) / max(left, right) * 100
    depth = (min(left, right) - middle) / min(left, right) * 100
    if rim_similarity <= 5 and 8 <= depth <= 35 and close >= right * 0.95:
        patterns.append({"name": "Cup / Rounded Base", "score": 72, "maturity": "Late Stage"})

    if not patterns:
        patterns.append({"name": "No High-Confidence Pattern", "score": 45, "maturity": "Unclear"})

    patterns = sorted(patterns, key=lambda item: item["score"], reverse=True)
    primary = patterns[0]

    failures = [
        f"Close below EMA21 (${ema21:.2f})",
        f"Loss of EMA50 structure (${ema50:.2f})",
        "Breakdown below the most recent higher low",
    ]

    return {
        "primary_pattern": primary["name"],
        "pattern_score": primary["score"],
        "patterns": patterns,
        "maturity": primary["maturity"],
        "failure_conditions": failures,
    }

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


def _trend_slope(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if len(clean) < 3:
        return 0.0
    x = np.arange(len(clean), dtype=float)
    return float(np.polyfit(x, clean.to_numpy(dtype=float), 1)[0])


def _swing_points(series: pd.Series, order: int = 2, mode: str = "high") -> list[tuple[int, float]]:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    points: list[tuple[int, float]] = []
    for index in range(order, len(values) - order):
        window = values[index - order:index + order + 1]
        value = values[index]
        if np.isnan(value):
            continue
        if mode == "high" and value == np.nanmax(window):
            points.append((index, float(value)))
        if mode == "low" and value == np.nanmin(window):
            points.append((index, float(value)))
    return points


def detect_patterns(df: pd.DataFrame) -> dict[str, Any]:
    """Deterministic swing-pattern recognition from OHLCV history.

    The engine reports candidates rather than claiming certainty. Pattern scores are
    structural heuristics and should be combined with trend, volume and risk data.
    """
    if df is None or len(df) < 60:
        return {
            "primary_pattern": "Insufficient Data",
            "pattern_score": None,
            "patterns": [],
            "maturity": "Unavailable",
            "failure_conditions": [],
            "sessions_since_signal": None,
        }

    data = df.copy().reset_index(drop=True)
    latest = data.iloc[-1]
    prev = data.iloc[-2]
    close = float(latest["close"])
    ema21 = float(latest["ema21"])
    ema50 = float(latest["ema50"])
    atr = float(latest["atr14"]) if _valid(latest.get("atr14")) else close * 0.04
    rvol = float(latest.get("rvol", 1.0)) if _valid(latest.get("rvol")) else 1.0
    atr_pct = atr / close * 100 if close else 0.0

    patterns: list[dict[str, Any]] = []

    # EMA21 reclaim with exact freshness.
    reclaim_index = None
    lookback = data.tail(20).reset_index()
    for idx in range(1, len(lookback)):
        if float(lookback.iloc[idx - 1]["close"]) <= float(lookback.iloc[idx - 1]["ema21"]) and float(lookback.iloc[idx]["close"]) > float(lookback.iloc[idx]["ema21"]):
            reclaim_index = int(lookback.iloc[idx]["index"])
    if reclaim_index is not None and close > ema21:
        sessions = len(data) - 1 - reclaim_index
        freshness_bonus = max(0, 12 - sessions * 2)
        score = 72 + freshness_bonus + min(10, max(0, (rvol - 1) * 8))
        patterns.append({"name": "EMA21 Reclaim", "score": round(min(score, 96)), "maturity": "Fresh" if sessions <= 2 else "Developing", "sessions_since_signal": sessions})

    # EMA21 retest / pullback.
    recent = data.tail(5)
    touched = bool((recent["low"] <= recent["ema21"] * 1.01).any())
    held = close >= ema21 and float(recent["close"].min()) >= float(recent["ema50"].min())
    if touched and held:
        distance = abs(close - ema21) / ema21 * 100
        score = max(55, 90 - distance * 8)
        patterns.append({"name": "EMA21 Retest", "score": round(score), "maturity": "Developing", "sessions_since_signal": 0})

    # Higher-low continuation.
    lows = data["low"].tail(25)
    first_low = float(lows.iloc[:12].min())
    second_low = float(lows.iloc[12:].min())
    if second_low > first_low and close > ema21 > ema50:
        patterns.append({"name": "Higher-Low Continuation", "score": 76, "maturity": "Confirmed", "sessions_since_signal": None})

    # Tight consolidation / bull flag proxy.
    last10 = data.tail(10)
    prior10 = data.iloc[-20:-10]
    recent_range = (float(last10["high"].max()) - float(last10["low"].min())) / close * 100
    prior_move = (float(prior10["close"].iloc[-1]) - float(prior10["close"].iloc[0])) / float(prior10["close"].iloc[0]) * 100
    volume_contract = float(last10["volume"].mean()) < float(prior10["volume"].mean())
    if prior_move >= 5 and recent_range <= max(8, atr_pct * 2.2) and volume_contract:
        patterns.append({"name": "Bull Flag / Tight Consolidation", "score": 82, "maturity": "Developing", "sessions_since_signal": None})

    # Pennant: strong pole followed by converging highs/lows.
    pennant = data.tail(18)
    pole = data.iloc[-30:-18]
    if len(pole) >= 8 and len(pennant) >= 12:
        pole_move = (float(pole["close"].iloc[-1]) - float(pole["close"].iloc[0])) / max(float(pole["close"].iloc[0]), 1e-9) * 100
        high_slope = _trend_slope(pennant["high"])
        low_slope = _trend_slope(pennant["low"])
        width_start = float(pennant["high"].iloc[:4].max() - pennant["low"].iloc[:4].min())
        width_end = float(pennant["high"].iloc[-4:].max() - pennant["low"].iloc[-4:].min())
        if pole_move >= 7 and high_slope < 0 < low_slope and width_end < width_start * 0.75:
            patterns.append({"name": "Bull Pennant", "score": 80, "maturity": "Near Breakout", "sessions_since_signal": None})

    # Triangle family.
    tri = data.tail(24)
    highs = tri["high"]
    lows24 = tri["low"]
    high_dispersion = float(highs.std()) / close * 100
    low_dispersion = float(lows24.std()) / close * 100
    high_slope = _trend_slope(highs)
    low_slope = _trend_slope(lows24)
    first_width = float(highs.iloc[:6].max() - lows24.iloc[:6].min())
    last_width = float(highs.iloc[-6:].max() - lows24.iloc[-6:].min())
    if high_dispersion <= 2.2 and low_slope > 0:
        patterns.append({"name": "Ascending Triangle", "score": 79, "maturity": "Near Breakout", "sessions_since_signal": None})
    if low_dispersion <= 2.2 and high_slope < 0:
        patterns.append({"name": "Descending Triangle", "score": 66, "maturity": "Developing", "sessions_since_signal": None})
    if high_slope < 0 < low_slope and last_width < first_width * 0.7:
        patterns.append({"name": "Symmetrical Triangle", "score": 73, "maturity": "Near Breakout", "sessions_since_signal": None})

    # Wedges: both boundaries slope same direction while converging.
    if last_width < first_width * 0.72:
        if high_slope < 0 and low_slope < 0 and abs(high_slope) > abs(low_slope):
            patterns.append({"name": "Falling Wedge", "score": 76, "maturity": "Developing", "sessions_since_signal": None})
        elif high_slope > 0 and low_slope > 0 and low_slope > high_slope:
            patterns.append({"name": "Rising Wedge", "score": 61, "maturity": "Developing", "sessions_since_signal": None})

    # Volatility contraction pattern (three progressively smaller ranges).
    vcp = data.tail(36)
    if len(vcp) == 36:
        ranges = []
        volumes = []
        for start in (0, 12, 24):
            segment = vcp.iloc[start:start + 12]
            ranges.append((float(segment["high"].max()) - float(segment["low"].min())) / close * 100)
            volumes.append(float(segment["volume"].mean()))
        if ranges[0] > ranges[1] > ranges[2] and volumes[0] > volumes[1] > volumes[2] and close > ema21:
            patterns.append({"name": "Volatility Contraction Pattern", "score": 84, "maturity": "Near Breakout", "sessions_since_signal": None})

    # Breakout base.
    prior_high = float(data["high"].iloc[-21:-1].max())
    if close > prior_high and rvol >= 1.2:
        score = min(96, 80 + (rvol - 1.2) * 10)
        patterns.append({"name": "Above-Average-Volume Breakout", "score": round(score), "maturity": "Triggered", "sessions_since_signal": 0})

    # Cup and cup-with-handle proxies.
    last60 = data.tail(60)
    left = float(last60["high"].iloc[:15].max())
    middle = float(last60["low"].iloc[20:40].min())
    right = float(last60["high"].iloc[-15:].max())
    rim_similarity = abs(left - right) / max(left, right) * 100
    depth = (min(left, right) - middle) / max(min(left, right), 1e-9) * 100
    if rim_similarity <= 5 and 8 <= depth <= 35 and close >= right * 0.95:
        handle = last60.tail(12)
        handle_depth = (float(handle["high"].max()) - float(handle["low"].min())) / max(float(handle["high"].max()), 1e-9) * 100
        name = "Cup & Handle" if handle_depth <= max(8, depth * 0.35) and float(handle["close"].iloc[-1]) >= float(handle["close"].iloc[0]) * 0.97 else "Cup / Rounded Base"
        patterns.append({"name": name, "score": 78 if name == "Cup & Handle" else 72, "maturity": "Late Stage", "sessions_since_signal": None})

    if not patterns:
        patterns.append({"name": "No High-Confidence Pattern", "score": 45, "maturity": "Unclear", "sessions_since_signal": None})

    # De-duplicate by name, preserving highest score.
    unique: dict[str, dict[str, Any]] = {}
    for item in patterns:
        if item["name"] not in unique or item["score"] > unique[item["name"]]["score"]:
            unique[item["name"]] = item
    patterns = sorted(unique.values(), key=lambda item: item["score"], reverse=True)
    primary = patterns[0]

    failures = [
        f"Close below EMA21 (${ema21:.2f})",
        f"Loss of EMA50 structure (${ema50:.2f})",
        "Breakdown below the most recent higher low",
        "Pattern boundary fails with expanding downside volume",
    ]

    return {
        "primary_pattern": primary["name"],
        "pattern_score": primary["score"],
        "patterns": patterns,
        "maturity": primary["maturity"],
        "failure_conditions": failures,
        "sessions_since_signal": primary.get("sessions_since_signal"),
    }

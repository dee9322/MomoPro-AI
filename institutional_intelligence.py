from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


def _clamp(value: float, low: float = 0, high: float = 100) -> int:
    return round(max(low, min(value, high)))


def get_institutional_activity(api_key: str, secret_key: str, symbol: str) -> dict[str, Any]:
    """Infer accumulation/distribution behavior from daily OHLCV.

    This detects institutional-style participation. It does not identify a
    specific institution or prove who placed the trades.
    """
    try:
        client = StockHistoricalDataClient(api_key, secret_key)
    except Exception:
        return {"status": "Unavailable", "score": None, "summary": "Alpaca could not initialize accumulation analysis."}
    end = datetime.now()
    start = end - timedelta(days=260)
    request = StockBarsRequest(
        symbol_or_symbols=symbol.upper(),
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )
    try:
        bars = client.get_stock_bars(request).df
    except Exception:
        return {"status": "Unavailable", "score": None, "summary": "Price/volume history was unavailable."}
    if bars.empty:
        return {"status": "Unavailable", "summary": "Price/volume history was unavailable."}

    df = bars.reset_index()
    if "symbol" in df.columns:
        df = df[df["symbol"] == symbol.upper()].copy()
    if len(df) < 35:
        return {"status": "Unavailable", "summary": "Not enough history for accumulation analysis."}

    df["prev_close"] = df["close"].shift(1)
    df["avg_volume20"] = df["volume"].rolling(20).mean()
    df["rvol"] = df["volume"] / df["avg_volume20"]
    df["daily_change_pct"] = (df["close"] / df["prev_close"] - 1) * 100
    df["range"] = (df["high"] - df["low"]).replace(0, np.nan)
    df["close_location"] = (df["close"] - df["low"]) / df["range"]

    recent = df.tail(30).dropna(subset=["rvol", "daily_change_pct", "close_location"])
    accumulation = recent[
        (recent["daily_change_pct"] > 0)
        & (recent["rvol"] >= 1.15)
        & (recent["close_location"] >= 0.60)
    ]
    distribution = recent[
        (recent["daily_change_pct"] < 0)
        & (recent["rvol"] >= 1.15)
        & (recent["close_location"] <= 0.40)
    ]

    up_volume = recent.loc[recent["daily_change_pct"] > 0, "volume"].sum()
    down_volume = recent.loc[recent["daily_change_pct"] < 0, "volume"].sum()
    volume_ratio = float(up_volume / down_volume) if down_volume > 0 else None
    positive_rvol = float(accumulation["rvol"].mean()) if not accumulation.empty else 0
    negative_rvol = float(distribution["rvol"].mean()) if not distribution.empty else 0

    score = 50
    score += min(len(accumulation) * 6, 30)
    score -= min(len(distribution) * 7, 35)
    if volume_ratio is not None:
        score += max(-15, min((volume_ratio - 1) * 20, 15))
    score += min(max(positive_rvol - 1, 0) * 10, 10)
    score -= min(max(negative_rvol - 1, 0) * 10, 10)
    score = _clamp(score)

    if score >= 75:
        verdict = "Accumulation"
    elif score >= 60:
        verdict = "Constructive"
    elif score >= 42:
        verdict = "Neutral"
    elif score >= 25:
        verdict = "Distribution Risk"
    else:
        verdict = "Distribution"

    summary = (
        f"Detected {len(accumulation)} accumulation-style day(s) and "
        f"{len(distribution)} distribution-style day(s) in the last 30 sessions."
    )

    return {
        "status": "Available",
        "score": score,
        "verdict": verdict,
        "accumulation_days": int(len(accumulation)),
        "distribution_days": int(len(distribution)),
        "up_down_volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "average_accumulation_rvol": round(positive_rvol, 2) if positive_rvol else None,
        "average_distribution_rvol": round(negative_rvol, 2) if negative_rvol else None,
        "source": "Alpaca IEX Daily OHLCV",
        "data_quality": "Calculated / Inferred",
        "summary": summary,
        "disclaimer": "OHLCV suggests institutional-style activity but cannot identify the actual buyer or seller.",
    }

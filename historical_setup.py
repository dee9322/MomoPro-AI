from __future__ import annotations
from typing import Any
import pandas as pd


def estimate_historical_setup(df: pd.DataFrame, pattern_name: str, horizon: int = 10) -> dict[str, Any]:
    """Transparent in-symbol historical analogue framework, not a full backtest."""
    if df is None or len(df) < 140:
        return {"sample_size": 0, "win_rate": None, "average_return": None, "average_drawdown": None, "note": "Insufficient history"}
    data = df.copy().reset_index(drop=True)
    outcomes = []
    drawdowns = []
    for i in range(55, len(data) - horizon):
        row = data.iloc[i]
        prev = data.iloc[i - 1]
        match = False
        if pattern_name == "EMA21 Reclaim":
            match = prev["close"] <= prev["ema21"] and row["close"] > row["ema21"]
        elif pattern_name == "EMA21 Retest":
            match = row["low"] <= row["ema21"] * 1.01 and row["close"] >= row["ema21"]
        elif pattern_name == "Above-Average-Volume Breakout":
            match = row["close"] > data["high"].iloc[i-20:i].max() and row.get("rvol", 0) >= 1.2
        else:
            match = row["close"] > row["ema21"] > row["ema50"] and row.get("macd_hist", 0) > 0
        if not match:
            continue
        entry = float(row["close"])
        future = data.iloc[i+1:i+1+horizon]
        exit_price = float(future.iloc[-1]["close"])
        outcomes.append((exit_price - entry) / entry * 100)
        drawdowns.append((float(future["low"].min()) - entry) / entry * 100)
    if not outcomes:
        return {"sample_size": 0, "win_rate": None, "average_return": None, "average_drawdown": None, "note": "No comparable historical samples"}
    wins = sum(1 for value in outcomes if value > 0)
    return {
        "sample_size": len(outcomes),
        "win_rate": round(wins / len(outcomes) * 100, 1),
        "average_return": round(sum(outcomes) / len(outcomes), 2),
        "average_drawdown": round(sum(drawdowns) / len(drawdowns), 2),
        "note": f"Same-symbol {horizon}-session analogue; descriptive, not predictive.",
    }

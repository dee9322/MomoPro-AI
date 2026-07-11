from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from indicators import calculate_indicators


def _analyze(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or len(df) < 55:
        return {"score": None, "trend": "Unavailable", "close": None}
    data = calculate_indicators(df.copy())
    latest = data.iloc[-1]
    score = 0
    if latest["close"] > latest["ema21"]: score += 25
    if latest["ema21"] > latest["ema50"]: score += 25
    if latest["macd_hist"] > 0: score += 20
    if latest["macd_hist"] > data.iloc[-2]["macd_hist"]: score += 15
    if 45 <= latest["rsi14"] <= 68: score += 15
    trend = "Bullish" if score >= 70 else "Constructive" if score >= 55 else "Mixed" if score >= 40 else "Bearish"
    return {"score": score, "trend": trend, "close": round(float(latest["close"]), 2)}


def get_multi_timeframe_confirmation(api_key: str, secret_key: str, symbol: str) -> dict[str, Any]:
    client = StockHistoricalDataClient(api_key, secret_key)
    now = datetime.now(timezone.utc)
    configs = {
        "Daily": (TimeFrame.Day, now - timedelta(days=360)),
        "4H": (TimeFrame(4, TimeFrameUnit.Hour), now - timedelta(days=180)),
        "1H": (TimeFrame.Hour, now - timedelta(days=60)),
        "15m": (TimeFrame(15, TimeFrameUnit.Minute), now - timedelta(days=20)),
    }
    results = {}
    for label, (timeframe, start) in configs.items():
        try:
            req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=timeframe, start=start, end=now, feed=DataFeed.IEX)
            raw = client.get_stock_bars(req).df
            if raw.empty:
                results[label] = {"score": None, "trend": "Unavailable", "close": None}
                continue
            df = raw.reset_index()
            if "symbol" in df.columns:
                df = df[df["symbol"] == symbol].copy()
            results[label] = _analyze(df)
        except Exception:
            results[label] = {"score": None, "trend": "Unavailable", "close": None}

    valid = [item["score"] for item in results.values() if item.get("score") is not None]
    overall = round(sum(valid) / len(valid)) if valid else None
    if overall is None:
        alignment = "Unavailable"
    elif overall >= 75:
        alignment = "Strong Alignment"
    elif overall >= 60:
        alignment = "Moderate Alignment"
    elif overall >= 45:
        alignment = "Mixed"
    else:
        alignment = "Conflict"
    return {"alignment_score": overall, "alignment": alignment, "timeframes": results}

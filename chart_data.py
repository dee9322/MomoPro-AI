from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from indicators import calculate_indicators


_TIMEFRAMES: dict[str, tuple[TimeFrame, timedelta]] = {
    "1D": (TimeFrame.Day, timedelta(days=540)),
    "4H": (TimeFrame(4, TimeFrameUnit.Hour), timedelta(days=240)),
    "1H": (TimeFrame.Hour, timedelta(days=90)),
    "15m": (TimeFrame(15, TimeFrameUnit.Minute), timedelta(days=30)),
    "5m": (TimeFrame(5, TimeFrameUnit.Minute), timedelta(days=10)),
}


def available_timeframes() -> list[str]:
    return list(_TIMEFRAMES)


def load_chart_bars(
    api_key: str,
    secret_key: str,
    symbol: str,
    timeframe_label: str = "1D",
    limit: int = 300,
) -> pd.DataFrame:
    symbol = str(symbol or "").upper().strip()
    if not symbol:
        raise ValueError("A ticker symbol is required.")
    if timeframe_label not in _TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe_label}")

    timeframe, lookback = _TIMEFRAMES[timeframe_label]
    end = datetime.now(timezone.utc)
    start = end - lookback
    client = StockHistoricalDataClient(api_key, secret_key)
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )
    raw = client.get_stock_bars(request).df
    if raw is None or raw.empty:
        return pd.DataFrame()

    frame = raw.reset_index()
    if "symbol" in frame.columns:
        frame = frame[frame["symbol"].astype(str).str.upper() == symbol].copy()
    timestamp_column = "timestamp" if "timestamp" in frame.columns else frame.columns[0]
    frame[timestamp_column] = pd.to_datetime(frame[timestamp_column], utc=True, errors="coerce")
    frame = frame.dropna(subset=[timestamp_column]).sort_values(timestamp_column)
    frame = frame.rename(columns={timestamp_column: "timestamp"})
    frame = calculate_indicators(frame)
    return frame.tail(max(50, int(limit))).reset_index(drop=True)


def latest_chart_snapshot(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {}
    row = frame.iloc[-1]
    keys = [
        "timestamp", "open", "high", "low", "close", "volume", "ema21", "ema50",
        "ema200", "rsi14", "macd", "macd_signal", "macd_hist", "rvol", "atr_pct",
    ]
    result: dict[str, Any] = {}
    for key in keys:
        value = row.get(key)
        if pd.isna(value):
            result[key] = None
        elif key == "timestamp":
            result[key] = pd.Timestamp(value).isoformat()
        else:
            result[key] = float(value)
    return result

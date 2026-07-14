from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from indicators import calculate_indicators
from pattern_engine import detect_patterns
from trend_health import calculate_trend_health
from timeframe_engine import get_multi_timeframe_confirmation
from entry_quality import calculate_entry_quality
from adaptive_stops import calculate_adaptive_stops
from target_engine import calculate_intelligent_targets
from exit_engine import calculate_exit_warnings
from historical_setup import estimate_historical_setup


def _daily_history(api_key: str, secret_key: str, symbol: str) -> pd.DataFrame:
    client = StockHistoricalDataClient(api_key, secret_key)
    end = datetime.now(timezone.utc)
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=end - timedelta(days=720),
        end=end,
        feed=DataFeed.IEX,
    )
    raw = client.get_stock_bars(req).df
    if raw.empty:
        return pd.DataFrame()
    df = raw.reset_index()
    if "symbol" in df.columns:
        df = df[df["symbol"] == symbol].copy()
    return calculate_indicators(df)


def get_trade_intelligence(api_key: str, secret_key: str, symbol: str, stock: Any) -> dict[str, Any]:
    try:
        daily = _daily_history(api_key, secret_key, symbol)
    except Exception:
        daily = pd.DataFrame()
    pattern = detect_patterns(daily)
    trend = calculate_trend_health(daily)
    timeframes = get_multi_timeframe_confirmation(api_key, secret_key, symbol)
    entry = calculate_entry_quality(stock, pattern, trend, timeframes)
    stops = calculate_adaptive_stops(stock)
    targets = calculate_intelligent_targets(stock, pattern)
    exits = calculate_exit_warnings(stock, trend, timeframes, pattern)
    historical = estimate_historical_setup(daily, pattern.get("primary_pattern", ""))
    available = sum([
        pattern.get("pattern_score") is not None,
        trend.get("score") is not None,
        timeframes.get("alignment_score") is not None,
        entry.get("score") is not None,
    ])
    overall = round(sum(v for v in [pattern.get("pattern_score"), trend.get("score"), timeframes.get("alignment_score"), entry.get("score")] if v is not None) / available) if available else None
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": overall,
        "status": "High Quality" if overall is not None and overall >= 80 else "Constructive" if overall is not None and overall >= 65 else "Developing" if overall is not None else "Unavailable",
        "pattern": pattern,
        "trend_health": trend,
        "multi_timeframe": timeframes,
        "entry_quality": entry,
        "adaptive_stops": stops,
        "targets": targets,
        "exit_management": exits,
        "historical_setup": historical,
    }

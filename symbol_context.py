from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from company_metadata import (
    attach_cached_metadata,
    available_cached_sectors,
    cached_company_metadata,
    enrich_company_metadata,
    enrich_company_metadata_batch,
    get_company_metadata,
)
from confidence import calculate_confidence
from indicators import calculate_indicators
from levels import calculate_levels
from risk_reward import calculate_risk_reward
from scoring import score_stock
from targets import calculate_targets


def normalize_stock_payload(stock: Any) -> dict[str, Any]:
    """Return one plain-dict contract for scanner rows and direct analyses.

    pandas Series, dataclasses/models exposing ``to_dict``, mappings and None are
    accepted. This is the only conversion path UI modules should use.
    """
    if stock is None:
        return {}
    if isinstance(stock, dict):
        return dict(stock)
    if isinstance(stock, Mapping):
        return dict(stock)
    converter = getattr(stock, "to_dict", None)
    if callable(converter):
        value = converter()
        return dict(value) if isinstance(value, Mapping) else {}
    try:
        return dict(stock)
    except (TypeError, ValueError):
        return {}


def analyze_symbol(api_key: str, secret_key: str, symbol: str) -> dict[str, Any]:
    """Build the same structural Stock Report row for any valid ticker.

    This removes the market scanner as a prerequisite. The scanner remains a
    discovery tool, while a direct search can create a complete report on demand.
    """
    ticker = str(symbol or "").upper().strip()
    if not ticker:
        raise ValueError("A ticker is required.")

    client = StockHistoricalDataClient(api_key, secret_key)
    end = datetime.now()
    start = end - timedelta(days=350)
    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )
    bars = client.get_stock_bars(request).df
    if bars is None or bars.empty:
        raise ValueError(f"No daily market data was returned for {ticker}.")
    data = bars.reset_index()
    if "symbol" in data.columns:
        data = data[data["symbol"] == ticker].copy()
    if len(data) < 50:
        raise ValueError(f"Not enough daily history is available for {ticker}.")

    data = calculate_indicators(data)
    latest, previous = data.iloc[-1], data.iloc[-2]
    levels = calculate_levels(data)
    risk_reward = calculate_risk_reward(latest["close"], levels)
    targets = calculate_targets(
        entry=risk_reward["Reference Entry"],
        risk_per_share=risk_reward["Risk Per Share"],
        levels=levels,
    )
    score, dee_fit, momo_score, modules, grade, setup, reasons = score_stock(latest, previous)
    confidence = calculate_confidence(modules=modules, risk_reward_data=risk_reward, levels=levels)

    row: dict[str, Any] = {
        "Symbol": ticker,
        "Close": round(float(latest["close"]), 2),
        "Score": score,
        "Dee Fit": dee_fit,
        "Setup": setup,
        "ATR %": round(float(latest.get("atr_pct", 0)), 2),
        "RVOL": round(float(latest.get("rvol", 0)), 2),
        "Distance EMA21 %": round(float(latest.get("distance_from_ema21", 0)), 2),
        "Reasons": reasons,
        "Grade": grade,
        "Momo Score": momo_score,
        "Momo Confidence": confidence["Momo Confidence"],
        "Confidence Rating": confidence["Confidence Rating"],
        "EMA21": round(float(latest.get("ema21", 0)), 2),
        "EMA50": round(float(latest.get("ema50", 0)), 2),
        "EMA200": round(float(latest.get("ema200", 0)), 2),
        "RSI": round(float(latest.get("rsi14", 0)), 2),
        "MACD": round(float(latest.get("macd", 0)), 4),
        "MACD Signal": round(float(latest.get("macd_signal", 0)), 4),
        "MACD Histogram": round(float(latest.get("macd_hist", 0)), 4),
    }
    for label in ("Trend", "Location", "Momentum", "Volume", "Opportunity", "Risk", "Structure"):
        row[f"{label} Confidence"] = confidence["Confidence Breakdown"][label]
    for n in (1, 2, 3):
        for side in ("Support", "Resistance"):
            row[f"{side} {n}"] = levels[f"{side} {n}"]
            row[f"{side} {n} Quality"] = levels[f"{side} {n} Quality"]
            row[f"{side} {n} Touches"] = levels[f"{side} {n} Touches"]
    for key in ("Reference Entry", "Risk Reference", "Reward Reference", "Risk Per Share", "Reward Per Share", "Risk Reward", "Risk Reward Status"):
        row[key] = risk_reward[key]
    for n in (1, 2, 3):
        row[f"T{n}"] = targets[f"T{n}"]
        row[f"T{n} Upside %"] = targets[f"T{n} Upside %"]
        row[f"T{n} R"] = targets[f"T{n} R"]
    return row


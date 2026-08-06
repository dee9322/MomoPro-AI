"""Fast, strategy-aware market pre-screening for the MomoPro scanner.

The pre-screen is intentionally permissive: its job is to choose which symbols
receive the expensive full MomoPro analysis, not to make the final trade
decision.  Hard liquidity gates previously removed quieter but technically
strong swing setups before the real scoring engine ever saw them.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


PRESCREEN_CALENDAR_DAYS = 180
MIN_PRESCREEN_BARS = 35
CHUNK_SIZE = 200


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if np.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _ema(series: pd.Series, span: int) -> float:
    if series.empty:
        return 0.0
    return _safe_float(series.ewm(span=span, adjust=False).mean().iloc[-1])


def _rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) <= period:
        return 50.0
    delta = series.diff()
    gains = delta.clip(lower=0).rolling(period).mean()
    losses = -delta.clip(upper=0).rolling(period).mean()
    loss = _safe_float(losses.iloc[-1])
    gain = _safe_float(gains.iloc[-1])
    if loss <= 0:
        return 100.0 if gain > 0 else 50.0
    rs = gain / loss
    return 100.0 - (100.0 / (1.0 + rs))


def _score_candidate(symbol: str, sdf: pd.DataFrame) -> dict[str, Any] | None:
    """Return a lightweight MomoPro-aligned ranking record for one symbol."""
    if len(sdf) < MIN_PRESCREEN_BARS:
        return None

    sdf = sdf.sort_values("timestamp")
    closes = pd.to_numeric(sdf["close"], errors="coerce").dropna()
    highs = pd.to_numeric(sdf["high"], errors="coerce")
    lows = pd.to_numeric(sdf["low"], errors="coerce")
    volumes = pd.to_numeric(sdf["volume"], errors="coerce").fillna(0)
    if len(closes) < MIN_PRESCREEN_BARS:
        return None

    close = _safe_float(closes.iloc[-1])
    if close < 3 or close > 50:
        return None

    previous_close = _safe_float(closes.iloc[-2], close)
    avg_volume = _safe_float(volumes.tail(20).mean())
    latest_volume = _safe_float(volumes.iloc[-1])
    avg_dollar_volume = close * avg_volume
    rvol = latest_volume / avg_volume if avg_volume > 0 else 0.0
    pct_change = ((close - previous_close) / previous_close * 100.0) if previous_close else 0.0

    ema21 = _ema(closes, 21)
    ema50 = _ema(closes, 50)
    ema200_proxy = _ema(closes, min(200, max(80, len(closes))))
    distance_ema21 = ((close - ema21) / ema21 * 100.0) if ema21 else 0.0
    rsi14 = _rsi(closes)

    true_range = pd.concat(
        [
            highs - lows,
            (highs - closes.shift(1)).abs(),
            (lows - closes.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_pct = (_safe_float(true_range.tail(14).mean()) / close * 100.0) if close else 0.0

    recent_high = _safe_float(highs.tail(20).max(), close)
    room_to_high = ((recent_high - close) / close * 100.0) if close else 0.0
    five_day_return = ((close - _safe_float(closes.iloc[-6], close)) / _safe_float(closes.iloc[-6], close) * 100.0) if len(closes) >= 6 else 0.0

    # Lightweight strategy score.  This intentionally mirrors the philosophy
    # of the full engine without duplicating its final decision logic.
    strategy_score = 0.0
    strategy_score += 18.0 if close > ema21 else 5.0
    strategy_score += 12.0 if ema21 > ema50 else 3.0
    strategy_score += 8.0 if ema50 > ema200_proxy else 2.0

    # Dee's preferred entry zone: near EMA21, not badly extended.
    if -1.5 <= distance_ema21 <= 4.0:
        strategy_score += 22.0
    elif -4.0 <= distance_ema21 <= 7.0:
        strategy_score += 12.0
    elif distance_ema21 > 10.0:
        strategy_score -= 10.0

    if 45.0 <= rsi14 <= 68.0:
        strategy_score += 12.0
    elif 38.0 <= rsi14 <= 75.0:
        strategy_score += 6.0

    if 3.0 <= atr_pct <= 12.0:
        strategy_score += 10.0
    elif 1.5 <= atr_pct <= 16.0:
        strategy_score += 5.0

    if room_to_high >= 4.0:
        strategy_score += 8.0
    elif room_to_high >= 2.0:
        strategy_score += 4.0

    if -3.0 <= five_day_return <= 12.0:
        strategy_score += 6.0

    # Liquidity matters, but it is a ranking input rather than an exclusionary
    # gate. Log scaling prevents mega-volume names from overwhelming setup fit.
    liquidity_score = min(20.0, max(0.0, np.log10(max(avg_dollar_volume, 1.0)) - 5.0) * 8.0)
    volume_score = min(8.0, max(0.0, rvol) * 4.0)
    activity_score = min(6.0, abs(pct_change) * 1.5)
    total_score = strategy_score + liquidity_score + volume_score + activity_score

    if avg_dollar_volume >= 5_000_000 and avg_volume >= 500_000:
        liquidity_tier = "strict"
    elif avg_dollar_volume >= 1_500_000 and avg_volume >= 150_000:
        liquidity_tier = "standard"
    else:
        liquidity_tier = "expanded"
        total_score -= 5.0

    return {
        "Symbol": symbol,
        "Prescreen Score": round(total_score, 4),
        "Strategy Score": round(strategy_score, 4),
        "Liquidity Score": round(liquidity_score, 4),
        "Liquidity Tier": liquidity_tier,
        "Close": close,
        "Average Volume": avg_volume,
        "Average Dollar Volume": avg_dollar_volume,
        "RVOL": rvol,
        "% Change": pct_change,
        "Distance EMA21 %": distance_ema21,
        "RSI": rsi14,
        "ATR %": atr_pct,
    }


def select_best_symbols(
    api_key: str,
    secret_key: str,
    symbols: list[str],
    limit: int = 500,
    *,
    return_diagnostics: bool = False,
):
    """Rank the broad universe and return up to ``limit`` symbols.

    Unlike the old implementation, this function does not require every symbol
    to pass a rigid 500k-share / $5m latest-dollar-volume gate.  It ranks every
    valid $3-$50 stock with enough history and fills the analysis pool from
    strict, standard, then expanded-liquidity candidates.
    """
    client = StockHistoricalDataClient(api_key, secret_key)
    end = datetime.now()
    start = end - timedelta(days=PRESCREEN_CALENDAR_DAYS)

    rows: list[dict[str, Any]] = []
    symbols_with_bars: set[str] = set()
    request_failures = 0

    for index in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[index:index + CHUNK_SIZE]
        try:
            request = StockBarsRequest(
                symbol_or_symbols=chunk,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed=DataFeed.IEX,
            )
            bars = client.get_stock_bars(request).df
            if bars.empty:
                continue

            frame = bars.reset_index()
            if "symbol" not in frame.columns:
                continue

            symbols_with_bars.update(frame["symbol"].astype(str).unique().tolist())
            for symbol, symbol_frame in frame.groupby("symbol", sort=False):
                record = _score_candidate(str(symbol), symbol_frame.copy())
                if record is not None:
                    rows.append(record)
        except Exception:
            request_failures += 1
            continue

    ranked = pd.DataFrame(rows)
    diagnostics = {
        "universe_count": len(symbols),
        "symbols_with_bars": len(symbols_with_bars),
        "eligible_count": 0,
        "strict_count": 0,
        "standard_count": 0,
        "expanded_count": 0,
        "selected_count": 0,
        "request_failures": request_failures,
        "target_count": int(limit),
    }

    if ranked.empty:
        selected = symbols[:limit]
        diagnostics["selected_count"] = len(selected)
        return (selected, diagnostics) if return_diagnostics else selected

    diagnostics["eligible_count"] = len(ranked)
    tier_counts = ranked["Liquidity Tier"].value_counts().to_dict()
    diagnostics["strict_count"] = int(tier_counts.get("strict", 0))
    diagnostics["standard_count"] = int(tier_counts.get("standard", 0))
    diagnostics["expanded_count"] = int(tier_counts.get("expanded", 0))

    tier_order = pd.Categorical(
        ranked["Liquidity Tier"],
        categories=["strict", "standard", "expanded"],
        ordered=True,
    )
    ranked = ranked.assign(__tier_order=tier_order)
    ranked = ranked.sort_values(
        by=["Prescreen Score", "Strategy Score", "Average Dollar Volume", "RVOL"],
        ascending=[False, False, False, False],
    )

    # The score already contains a modest liquidity penalty, so global ranking
    # preserves strong quieter setups while still favoring tradeable names.
    selected = ranked.head(limit)["Symbol"].astype(str).tolist()
    diagnostics["selected_count"] = len(selected)

    return (selected, diagnostics) if return_diagnostics else selected

"""Fast two-stage, strategy-aware market pre-screening for MomoPro.

Stage 1 is deliberately cheap and permissive across the broad U.S. universe.
Stage 2 performs lightweight MomoPro-aligned ranking only on a manageable pool.
The best symbols then receive the expensive full scanner analysis in scanner.py.
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

# Broad pass: enough recent bars to establish tradeability/activity without
# downloading months of history for ~27k assets.
BROAD_CALENDAR_DAYS = 55
BROAD_MIN_BARS = 15
BROAD_CHUNK_SIZE = 1000
BROAD_POOL_TARGET = 3000

# Strategy pass: enough history for EMA50/RSI/ATR and swing-setup context.
STRATEGY_CALENDAR_DAYS = 125
STRATEGY_MIN_BARS = 45
STRATEGY_CHUNK_SIZE = 500


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


def _broad_record(symbol: str, sdf: pd.DataFrame) -> dict[str, Any] | None:
    """Cheap permissive pass. Never tries to make the final trade decision."""
    if len(sdf) < BROAD_MIN_BARS:
        return None
    sdf = sdf.sort_values("timestamp")
    closes = pd.to_numeric(sdf["close"], errors="coerce").dropna()
    volumes = pd.to_numeric(sdf["volume"], errors="coerce").fillna(0)
    highs = pd.to_numeric(sdf["high"], errors="coerce")
    lows = pd.to_numeric(sdf["low"], errors="coerce")
    if len(closes) < BROAD_MIN_BARS:
        return None

    close = _safe_float(closes.iloc[-1])
    if not 3 <= close <= 50:
        return None

    avg_volume = _safe_float(volumes.tail(15).mean())
    dollar_volume = close * avg_volume

    # Very permissive safety floor. This removes genuinely untradeable names,
    # not quieter swing setups. SLS-like names comfortably survive this gate.
    if avg_volume < 50_000 and dollar_volume < 500_000:
        return None

    prev = _safe_float(closes.iloc[-2], close)
    day_move = abs((close - prev) / prev * 100.0) if prev else 0.0
    first = _safe_float(closes.iloc[max(0, len(closes) - 10)], close)
    ten_day_move = abs((close - first) / first * 100.0) if first else 0.0
    recent_range = ((_safe_float(highs.tail(15).max(), close) - _safe_float(lows.tail(15).min(), close)) / close * 100.0) if close else 0.0

    # Log liquidity prevents mega-caps from dominating. Movement/range bonuses
    # keep active swing names in the pool without requiring high RVOL today.
    liquidity = max(0.0, np.log10(max(dollar_volume, 1.0)) - 5.0) * 10.0
    broad_score = liquidity + min(day_move, 8.0) * 1.25 + min(ten_day_move, 25.0) * 0.45 + min(recent_range, 35.0) * 0.30
    return {"Symbol": symbol, "Broad Score": broad_score, "Dollar Volume": dollar_volume}


def _strategy_record(symbol: str, sdf: pd.DataFrame) -> dict[str, Any] | None:
    if len(sdf) < STRATEGY_MIN_BARS:
        return None
    sdf = sdf.sort_values("timestamp")
    closes = pd.to_numeric(sdf["close"], errors="coerce").dropna()
    highs = pd.to_numeric(sdf["high"], errors="coerce")
    lows = pd.to_numeric(sdf["low"], errors="coerce")
    volumes = pd.to_numeric(sdf["volume"], errors="coerce").fillna(0)
    if len(closes) < STRATEGY_MIN_BARS:
        return None

    close = _safe_float(closes.iloc[-1])
    if not 3 <= close <= 50:
        return None
    previous_close = _safe_float(closes.iloc[-2], close)
    avg_volume = _safe_float(volumes.tail(20).mean())
    latest_volume = _safe_float(volumes.iloc[-1])
    avg_dollar_volume = close * avg_volume
    rvol = latest_volume / avg_volume if avg_volume > 0 else 0.0
    pct_change = ((close - previous_close) / previous_close * 100.0) if previous_close else 0.0

    ema21 = _ema(closes, 21)
    ema50 = _ema(closes, 50)
    # This is only a pre-rank. The real scanner later calculates true EMA200
    # from >=220 bars; don't download 300+ calendar days for thousands here.
    ema_long = _ema(closes, min(80, len(closes)))
    distance_ema21 = ((close - ema21) / ema21 * 100.0) if ema21 else 0.0
    rsi14 = _rsi(closes)

    true_range = pd.concat([highs - lows, (highs - closes.shift(1)).abs(), (lows - closes.shift(1)).abs()], axis=1).max(axis=1)
    atr_pct = (_safe_float(true_range.tail(14).mean()) / close * 100.0) if close else 0.0
    recent_high = _safe_float(highs.tail(20).max(), close)
    room_to_high = ((recent_high - close) / close * 100.0) if close else 0.0
    base = _safe_float(closes.iloc[-6], close) if len(closes) >= 6 else close
    five_day_return = ((close - base) / base * 100.0) if base else 0.0

    strategy = 0.0
    strategy += 18 if close > ema21 else 5
    strategy += 12 if ema21 > ema50 else 3
    strategy += 8 if ema50 > ema_long else 2
    if -1.5 <= distance_ema21 <= 4.0: strategy += 22
    elif -4.0 <= distance_ema21 <= 7.0: strategy += 12
    elif distance_ema21 > 10.0: strategy -= 10
    if 45 <= rsi14 <= 68: strategy += 12
    elif 38 <= rsi14 <= 75: strategy += 6
    if 3 <= atr_pct <= 12: strategy += 10
    elif 1.5 <= atr_pct <= 16: strategy += 5
    if room_to_high >= 4: strategy += 8
    elif room_to_high >= 2: strategy += 4
    if -3 <= five_day_return <= 12: strategy += 6

    liquidity = min(20.0, max(0.0, np.log10(max(avg_dollar_volume, 1.0)) - 5.0) * 8.0)
    volume = min(8.0, max(0.0, rvol) * 4.0)
    activity = min(6.0, abs(pct_change) * 1.5)
    total = strategy + liquidity + volume + activity
    if avg_dollar_volume < 1_500_000 and avg_volume < 150_000:
        total -= 5.0

    return {
        "Symbol": symbol, "Prescreen Score": total, "Strategy Score": strategy,
        "Average Dollar Volume": avg_dollar_volume, "RVOL": rvol,
    }


def _fetch_rank(client, symbols, start, end, chunk_size, scorer):
    rows = []
    symbols_with_bars = set()
    failures = 0
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i + chunk_size]
        try:
            req = StockBarsRequest(symbol_or_symbols=chunk, timeframe=TimeFrame.Day, start=start, end=end, feed=DataFeed.IEX)
            bars = client.get_stock_bars(req).df
            if bars.empty:
                continue
            frame = bars.reset_index()
            if "symbol" not in frame.columns:
                continue
            symbols_with_bars.update(frame["symbol"].astype(str).unique())
            for symbol, sdf in frame.groupby("symbol", sort=False):
                rec = scorer(str(symbol), sdf)
                if rec is not None:
                    rows.append(rec)
        except Exception:
            failures += 1
    return rows, symbols_with_bars, failures


def select_best_symbols(api_key: str, secret_key: str, symbols: list[str], limit: int = 500, *, return_diagnostics: bool = False):
    """Fast broad pass -> strategy-aware pool -> best ``limit`` for full scan."""
    client = StockHistoricalDataClient(api_key, secret_key)
    end = datetime.now()

    broad_rows, broad_bars, broad_failures = _fetch_rank(
        client, symbols, end - timedelta(days=BROAD_CALENDAR_DAYS), end,
        BROAD_CHUNK_SIZE, _broad_record,
    )
    broad = pd.DataFrame(broad_rows)
    diagnostics = {
        "universe_count": len(symbols), "symbols_with_bars": len(broad_bars),
        "eligible_count": len(broad), "broad_pool_count": 0,
        "strategy_eligible_count": 0, "selected_count": 0,
        "request_failures": broad_failures, "target_count": int(limit),
    }
    if broad.empty:
        selected = symbols[:limit]
        diagnostics["selected_count"] = len(selected)
        return (selected, diagnostics) if return_diagnostics else selected

    broad = broad.sort_values(["Broad Score", "Dollar Volume"], ascending=[False, False])
    pool_size = min(len(broad), max(BROAD_POOL_TARGET, int(limit) * 5))
    pool = broad.head(pool_size)["Symbol"].astype(str).tolist()
    diagnostics["broad_pool_count"] = len(pool)

    strategy_rows, strategy_bars, strategy_failures = _fetch_rank(
        client, pool, end - timedelta(days=STRATEGY_CALENDAR_DAYS), end,
        STRATEGY_CHUNK_SIZE, _strategy_record,
    )
    diagnostics["request_failures"] += strategy_failures
    diagnostics["strategy_eligible_count"] = len(strategy_rows)

    ranked = pd.DataFrame(strategy_rows)
    if ranked.empty:
        selected = pool[:limit]
    else:
        ranked = ranked.sort_values(
            ["Prescreen Score", "Strategy Score", "Average Dollar Volume", "RVOL"],
            ascending=[False, False, False, False],
        )
        selected = ranked.head(limit)["Symbol"].astype(str).tolist()

    diagnostics["selected_count"] = len(selected)
    return (selected, diagnostics) if return_diagnostics else selected

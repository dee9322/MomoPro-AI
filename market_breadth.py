from __future__ import annotations

import gc
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from market_universe import get_market_universe
from pre_screener import select_best_symbols


BREADTH_UNIVERSE_LIMIT = 500
BREADTH_HISTORY_DAYS = 330
BREADTH_MINIMUM_BARS = 220
BREADTH_CHUNK_SIZE = 25


def _empty_breadth(message: str) -> dict[str, Any]:
    return {
        "status": "Unavailable",
        "breadth_score": None,
        "breadth_status": "Unavailable",
        "summary": message,
        "advancing": 0,
        "declining": 0,
        "unchanged": 0,
        "advance_decline_ratio": None,
        "advance_pct": None,
        "decline_pct": None,
        "above_ema21": 0,
        "above_ema21_pct": None,
        "above_ema50": 0,
        "above_ema50_pct": None,
        "above_ema200": 0,
        "above_ema200_pct": None,
        "new_20_day_highs": 0,
        "new_20_day_lows": 0,
        "high_low_ratio": None,
        "stocks_analyzed": 0,
        "universe_label": "Top 500 liquid eligible stocks",
    }


def _pct(value: int, total: int) -> float | None:
    return round((value / total) * 100, 1) if total else None


def get_market_breadth(api_key: str, secret_key: str) -> dict[str, Any]:
    """Calculate breadth from the same liquid 500-stock universe used by the scanner."""
    try:
        all_symbols = get_market_universe(limit=None)
        symbols = select_best_symbols(
            api_key,
            secret_key,
            all_symbols,
            limit=BREADTH_UNIVERSE_LIMIT,
        )

        client = StockHistoricalDataClient(api_key, secret_key)
        end = datetime.now()
        start = end - timedelta(days=BREADTH_HISTORY_DAYS)

        advancing = declining = unchanged = 0
        above_ema21 = above_ema50 = above_ema200 = 0
        new_highs = new_lows = 0
        analyzed = 0

        for batch_start in range(0, len(symbols), BREADTH_CHUNK_SIZE):
            chunk = symbols[batch_start : batch_start + BREADTH_CHUNK_SIZE]
            bars = None
            frame = None

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

                for symbol in chunk:
                    sdf = frame[frame["symbol"] == symbol].copy()
                    if len(sdf) < BREADTH_MINIMUM_BARS:
                        continue

                    close = sdf["close"]
                    latest = float(close.iloc[-1])
                    previous = float(close.iloc[-2])
                    ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
                    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
                    ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
                    prior_20_high = float(sdf["high"].iloc[-21:-1].max())
                    prior_20_low = float(sdf["low"].iloc[-21:-1].min())

                    analyzed += 1
                    if latest > previous:
                        advancing += 1
                    elif latest < previous:
                        declining += 1
                    else:
                        unchanged += 1

                    above_ema21 += int(latest > ema21)
                    above_ema50 += int(latest > ema50)
                    above_ema200 += int(latest > ema200)
                    new_highs += int(latest >= prior_20_high)
                    new_lows += int(latest <= prior_20_low)

            except Exception:
                continue
            finally:
                if frame is not None:
                    del frame
                if bars is not None:
                    del bars
                gc.collect()

        if analyzed == 0:
            return _empty_breadth("No breadth data could be calculated.")

        advance_pct = _pct(advancing, analyzed)
        decline_pct = _pct(declining, analyzed)
        ema21_pct = _pct(above_ema21, analyzed)
        ema50_pct = _pct(above_ema50, analyzed)
        ema200_pct = _pct(above_ema200, analyzed)

        ad_ratio = round(advancing / declining, 2) if declining else None
        high_low_ratio = round(new_highs / new_lows, 2) if new_lows else None

        participation = (
            (advance_pct or 0) * 0.30
            + (ema21_pct or 0) * 0.25
            + (ema50_pct or 0) * 0.25
            + (ema200_pct or 0) * 0.20
        )

        if new_highs > new_lows:
            participation += min((new_highs - new_lows) * 0.15, 8)
        elif new_lows > new_highs:
            participation -= min((new_lows - new_highs) * 0.15, 8)

        breadth_score = round(max(0, min(participation, 100)))

        if breadth_score >= 75:
            breadth_status = "Healthy"
        elif breadth_score >= 58:
            breadth_status = "Constructive"
        elif breadth_score >= 42:
            breadth_status = "Mixed"
        elif breadth_score >= 25:
            breadth_status = "Weak"
        else:
            breadth_status = "Deteriorating"

        summary = (
            f"{advancing} stocks advanced and {declining} declined. "
            f"{ema21_pct:.1f}% are above EMA21, {ema50_pct:.1f}% above EMA50, "
            f"and {ema200_pct:.1f}% above EMA200. "
            f"There were {new_highs} new 20-day highs versus {new_lows} new 20-day lows."
        )

        return {
            "status": "Available",
            "breadth_score": breadth_score,
            "breadth_status": breadth_status,
            "summary": summary,
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "advance_decline_ratio": ad_ratio,
            "advance_pct": advance_pct,
            "decline_pct": decline_pct,
            "above_ema21": above_ema21,
            "above_ema21_pct": ema21_pct,
            "above_ema50": above_ema50,
            "above_ema50_pct": ema50_pct,
            "above_ema200": above_ema200,
            "above_ema200_pct": ema200_pct,
            "new_20_day_highs": new_highs,
            "new_20_day_lows": new_lows,
            "high_low_ratio": high_low_ratio,
            "stocks_analyzed": analyzed,
            "universe_label": "Top 500 liquid eligible stocks",
        }

    except Exception as error:
        return _empty_breadth(f"Breadth data unavailable: {error}")

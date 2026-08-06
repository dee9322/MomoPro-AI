from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from indicators import calculate_indicators
from trade_models import TradeRecord


def _dt(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _grade(score: float) -> str:
    return (
        "A" if score >= 90 else "A-" if score >= 85 else "B+" if score >= 80
        else "B" if score >= 75 else "B-" if score >= 70 else "C+" if score >= 65
        else "C" if score >= 55 else "D"
    )


def _load_bars(client, symbol: str, timeframe, start: datetime, end: datetime) -> pd.DataFrame:
    raw = client.get_stock_bars(
        StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )
    ).df
    if raw is None or raw.empty:
        return pd.DataFrame()
    frame = raw.reset_index()
    if "symbol" in frame.columns:
        frame = frame[frame["symbol"].astype(str).str.upper() == symbol].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp")
    return calculate_indicators(frame)


def _row_number(row, name: str, default: float = 0.0) -> float:
    value = row.get(name, default)
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _daily_score(price: float, row) -> tuple[float, dict]:
    ema21 = _row_number(row, "ema21", price)
    ema50 = _row_number(row, "ema50", price)
    ema200 = _row_number(row, "ema200", price)
    rsi = _row_number(row, "rsi14", 50)
    rvol = _row_number(row, "rvol", 0)
    atr_pct = _row_number(row, "atr_pct", 0)
    distance = ((price - ema21) / ema21 * 100) if ema21 else 0

    score = 0.0
    score += 18 if price >= ema21 else 5
    score += 16 if ema21 > ema50 else 4
    score += 12 if ema50 > ema200 else 3
    score += 10 if abs(distance) <= 3 else 5 if abs(distance) <= 6 else 0
    score += 9 if 45 <= rsi <= 68 else 5 if 38 <= rsi <= 75 else 1
    score += 10 if rvol >= 1.1 else 6 if rvol >= 0.8 else 2 if rvol >= 0.6 else 0
    score += 5 if atr_pct >= 4 else 3 if atr_pct >= 2 else 1
    score = min(80, score)
    return score, {
        "entry_price": round(price, 4),
        "ema21": round(ema21, 4),
        "ema50": round(ema50, 4),
        "ema200": round(ema200, 4),
        "distance_from_ema21_pct": round(distance, 2),
        "rsi14": round(rsi, 2),
        "rvol": round(rvol, 2),
        "atr_pct": round(atr_pct, 2),
    }


def _intraday_score(price: float, row) -> tuple[float, dict]:
    ema21 = _row_number(row, "ema21", price)
    ema50 = _row_number(row, "ema50", price)
    rsi = _row_number(row, "rsi14", 50)
    rvol = _row_number(row, "rvol", 0)
    distance = ((price - ema21) / ema21 * 100) if ema21 else 0
    score = 0.0
    score += 8 if price >= ema21 else 2
    score += 6 if ema21 >= ema50 else 1
    score += 4 if abs(distance) <= 2 else 2 if abs(distance) <= 4 else 0
    score += 2 if 40 <= rsi <= 72 else 0
    score = min(20, score)
    return score, {
        "entry_price": round(price, 4),
        "ema21": round(ema21, 4),
        "ema50": round(ema50, 4),
        "distance_from_ema21_pct": round(distance, 2),
        "rsi14": round(rsi, 2),
        "rvol": round(rvol, 2),
    }


def reconstruct_trade(trade: TradeRecord, api_key: str, secret_key: str) -> dict:
    entry = _dt(trade.entry_date)
    symbol = trade.symbol.upper()
    client = StockHistoricalDataClient(api_key, secret_key)

    daily = _load_bars(client, symbol, TimeFrame.Day, entry - timedelta(days=420), entry + timedelta(days=1))
    if daily.empty:
        raise RuntimeError("No historical daily candles were returned for this trade.")

    # The entry-day daily candle contains data from after the entry. Use only the
    # last fully completed daily candle before the entry date.
    entry_day = pd.Timestamp(entry).tz_convert("UTC").date()
    daily_frozen = daily[daily["timestamp"].dt.date < entry_day].copy()
    if daily_frozen.empty:
        raise RuntimeError("No completed daily candle existed before the entry timestamp.")
    daily_row = daily_frozen.iloc[-1]

    intraday = pd.DataFrame()
    intraday_label = "5m"
    bar_minutes = 5
    for timeframe, label, minutes, lookback in (
        (TimeFrame(5, TimeFrameUnit.Minute), "5m", 5, 35),
        (TimeFrame(15, TimeFrameUnit.Minute), "15m", 15, 60),
        (TimeFrame.Hour, "1H", 60, 120),
    ):
        candidate = _load_bars(client, symbol, timeframe, entry - timedelta(days=lookback), entry + timedelta(minutes=minutes))
        if candidate.empty:
            continue
        # Only use fully completed bars. A bar stamped 11:00 is not available at
        # 11:02 if it closes at 11:05.
        completed_cutoff = pd.Timestamp(entry) - pd.Timedelta(minutes=minutes)
        frozen = candidate[candidate["timestamp"] <= completed_cutoff].copy()
        if not frozen.empty:
            intraday = frozen
            intraday_label = label
            bar_minutes = minutes
            break

    price = float(trade.entry_price)
    daily_points, daily_context = _daily_score(price, daily_row)
    intraday_points = 0.0
    intraday_context = {}
    intraday_as_of = None
    if not intraday.empty:
        intraday_row = intraday.iloc[-1]
        intraday_points, intraday_context = _intraday_score(price, intraday_row)
        intraday_as_of = pd.Timestamp(intraday_row["timestamp"]).isoformat()

    score = round(max(0, min(100, daily_points + intraday_points)), 1)
    daily_distance = abs(float(daily_context.get("distance_from_ema21_pct", 99)))
    daily_bullish = daily_context["ema21"] > daily_context["ema50"]
    if price >= daily_context["ema21"] and daily_distance <= 3:
        setup = "EMA21 Reclaim / Continuation"
        setup_confidence = 92 if daily_bullish else 80
    elif price > daily_context["ema21"] > daily_context["ema50"]:
        setup = "Trend Continuation"
        setup_confidence = 84
    else:
        setup = "Pullback / Reversal Candidate"
        setup_confidence = 68

    evidence_confidence = 96 if not intraday.empty else 78
    reconstruction_quality = "Excellent" if evidence_confidence >= 90 else "Good" if evidence_confidence >= 75 else "Limited"
    chart_snapshot = [
        {
            "timestamp": pd.Timestamp(row["timestamp"]).isoformat(),
            "close": round(float(row["close"]), 4),
        }
        for _, row in daily_frozen.tail(90).iterrows()
        if pd.notna(row.get("close"))
    ]

    result = {
        "entry_execution_time": entry.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "daily_context_as_of": pd.Timestamp(daily_row["timestamp"]).isoformat(),
        "intraday_context_as_of": intraday_as_of,
        "intraday_timeframe": intraday_label if not intraday.empty else "Unavailable",
        "objective_entry_score": score,
        "objective_entry_grade": _grade(score),
        "likely_setup": setup,
        "setup_confidence": float(setup_confidence),
        "evidence_confidence": float(evidence_confidence),
        "reconstruction_quality": reconstruction_quality,
        "daily_context": daily_context,
        "intraday_execution_context": intraday_context,
        "personal_thesis": "Unknown — not recorded",
        "planned_targets": "Unknown — not recorded" if not any([trade.t1, trade.t2, trade.t3]) else "Available from journal",
        "rule_following": "Not gradable without a verified pre-entry plan",
        "chart_snapshot": chart_snapshot,
        "hindsight_guard": (
            "Daily grading used only fully completed candles before the entry date. "
            f"Intraday timing used only completed {intraday_label} bars before the exact broker execution time."
        ),
    }
    trade.reconstruction = result
    return result

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd

from confidence import calculate_confidence
from indicators import calculate_indicators
from levels import calculate_levels
from massive_market_data import MINIMUM_READY_SESSIONS, history_status, load_history
from risk_reward import calculate_risk_reward
from scoring import score_stock
from targets import calculate_targets

SCAN_LIMIT = 500
MINIMUM_DAILY_BARS = 220


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _valid_symbol(symbol: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{1,5}", symbol or ""))


def _ema(series: pd.Series, span: int) -> float:
    return _f(series.ewm(span=span, adjust=False).mean().iloc[-1])


def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1 / period, adjust=False).mean()
    denominator = _f(loss.iloc[-1])
    if denominator <= 0:
        return 100.0 if _f(gain.iloc[-1]) > 0 else 50.0
    rs = _f(gain.iloc[-1]) / denominator
    return 100 - 100 / (1 + rs)


def _preliminary_record(symbol: str, sdf: pd.DataFrame) -> dict[str, Any] | None:
    if not _valid_symbol(symbol) or len(sdf) < MINIMUM_DAILY_BARS:
        return None
    sdf = sdf.sort_values("date")
    close = pd.to_numeric(sdf["close"], errors="coerce")
    high = pd.to_numeric(sdf["high"], errors="coerce")
    low = pd.to_numeric(sdf["low"], errors="coerce")
    volume = pd.to_numeric(sdf["volume"], errors="coerce").fillna(0)
    if close.isna().sum() or len(close) < MINIMUM_DAILY_BARS:
        return None
    price = _f(close.iloc[-1])
    if not 3 <= price <= 50:
        return None

    ema21, ema50, ema200 = _ema(close, 21), _ema(close, 50), _ema(close, 200)
    distance = ((price - ema21) / ema21 * 100) if ema21 else 99.0
    rsi = _rsi(close)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = _f((macd_line - macd_signal).iloc[-1])
    prior_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prior_close).abs(), (low - prior_close).abs()], axis=1).max(axis=1)
    atr_pct = (_f(tr.tail(14).mean()) / price * 100) if price else 0.0
    avg_volume = _f(volume.tail(20).mean())
    rvol = _f(volume.iloc[-1]) / avg_volume if avg_volume else 0.0
    dollar_volume = price * avg_volume
    recent_high = _f(high.tail(20).max(), price)
    room = (recent_high - price) / price * 100 if price else 0.0
    range_now = _f((high.tail(5) - low.tail(5)).mean())
    range_prior = _f((high.tail(20) - low.tail(20)).mean())
    contraction = range_now / range_prior if range_prior else 1.0

    score = 0.0
    bucket = "Emerging Setup"
    if price > ema21: score += 18
    if ema21 > ema50: score += 14
    if ema50 > ema200: score += 12
    if -1.5 <= distance <= 4.0:
        score += 24
        bucket = "EMA21 Pullback"
    elif -4 <= distance <= 7:
        score += 12
    elif distance > 10:
        score -= 12
    if close.iloc[-2] <= _f(close.ewm(span=21, adjust=False).mean().iloc[-2]) and price > ema21:
        score += 12
        bucket = "Fresh EMA21 Reclaim"
    if 43 <= rsi <= 68: score += 12
    elif 35 <= rsi <= 75: score += 5
    if macd_hist > 0: score += 8
    if 3 <= atr_pct <= 12: score += 10
    elif 1.5 <= atr_pct <= 16: score += 5
    if room >= 4: score += 7
    if contraction < 0.75:
        score += 10
        bucket = "Volatility Contraction"
    if price > ema21 > ema50 > ema200 and 0 <= distance <= 6:
        bucket = "Continuation"
    score += min(12.0, max(0.0, np.log10(max(dollar_volume, 1)) - 5) * 5)
    score += min(6.0, max(0.0, rvol) * 3)
    if avg_volume < 75_000 and dollar_volume < 750_000:
        score -= 8

    return {
        "Symbol": symbol,
        "Preliminary Score": score,
        "Bucket": bucket,
        "Close": price,
        "EMA21": ema21,
        "EMA50": ema50,
        "EMA200": ema200,
        "RSI": rsi,
        "ATR %": atr_pct,
        "RVOL": rvol,
        "Distance EMA21 %": distance,
        "Dollar Volume": dollar_volume,
    }


def rank_universe(history: pd.DataFrame, limit: int = SCAN_LIMIT) -> tuple[list[str], pd.DataFrame, dict[str, Any]]:
    records = []
    usable = 0
    for symbol, sdf in history.groupby("symbol", sort=False):
        if len(sdf) >= MINIMUM_DAILY_BARS:
            usable += 1
        rec = _preliminary_record(str(symbol), sdf)
        if rec:
            records.append(rec)
    ranked = pd.DataFrame(records)
    if ranked.empty:
        raise RuntimeError("Scanner v2 could not find eligible $3-$50 common-stock histories in the stored market database.")

    ranked = ranked.sort_values(["Preliminary Score", "Dollar Volume"], ascending=[False, False])
    # Reserve space for every setup family so activity alone cannot dominate.
    selected: list[str] = []
    bucket_quota = max(40, limit // 8)
    for bucket in ["Fresh EMA21 Reclaim", "EMA21 Pullback", "Volatility Contraction", "Continuation", "Emerging Setup"]:
        for symbol in ranked.loc[ranked["Bucket"] == bucket, "Symbol"].head(bucket_quota):
            if symbol not in selected:
                selected.append(symbol)
    for symbol in ranked["Symbol"]:
        if len(selected) >= limit:
            break
        if symbol not in selected:
            selected.append(symbol)
    return selected[:limit], ranked, {
        "universe_count": int(history["symbol"].nunique()),
        "usable_history_count": usable,
        "eligible_count": len(ranked),
        "selected_count": min(limit, len(selected)),
    }


def run_scan_v2() -> pd.DataFrame:
    status = history_status()
    if not status["ready"]:
        raise RuntimeError(
            f"Scanner v2 market database is not ready ({status['sessions']}/{MINIMUM_READY_SESSIONS} required sessions). "
            "Open Scanner v2 Market Database and build or continue history first."
        )
    history = load_history()
    symbols, ranking, diagnostics = rank_universe(history, SCAN_LIMIT)
    ranking_map = ranking.set_index("Symbol").to_dict(orient="index")
    groups = {symbol: frame.sort_values("date") for symbol, frame in history[history["symbol"].isin(symbols)].groupby("symbol", sort=False)}
    results = []

    for symbol in symbols:
        try:
            raw = groups.get(symbol)
            if raw is None or len(raw) < MINIMUM_DAILY_BARS:
                continue
            symbol_df = raw.rename(columns={"date": "timestamp"}).copy()
            symbol_df["timestamp"] = pd.to_datetime(symbol_df["timestamp"])
            symbol_df = calculate_indicators(symbol_df)
            latest, previous = symbol_df.iloc[-1], symbol_df.iloc[-2]
            required = [latest.get("ema200"), latest.get("rsi14"), latest.get("macd_hist"), latest.get("atr_pct"), latest.get("rvol"), latest.get("prior_120_high")]
            if any(pd.isna(value) for value in required):
                continue
            levels = calculate_levels(symbol_df)
            risk_reward = calculate_risk_reward(latest["close"], levels)
            targets = calculate_targets(entry=risk_reward["Reference Entry"], risk_per_share=risk_reward["Risk Per Share"], levels=levels)
            score, dee_fit, momo_score, modules, grade, setup, reasons = score_stock(latest, previous)
            confidence = calculate_confidence(modules=modules, risk_reward_data=risk_reward, levels=levels)
            pre = ranking_map.get(symbol, {})
            row = {
                "Symbol": symbol,
                "__Universe Count": diagnostics["universe_count"],
                "__Prescreened Count": diagnostics["selected_count"],
                "__Prescreen Eligible Count": diagnostics["eligible_count"],
                "__Prescreen Bars Count": diagnostics["usable_history_count"],
                "__Prescreen Strict Count": 0,
                "__Prescreen Standard Count": 0,
                "__Prescreen Expanded Count": 0,
                "__Prescreen Request Failures": 0,
                "__Usable History Count": diagnostics["usable_history_count"],
                "Close": round(_f(latest["close"]), 2),
                "Score": score,
                "Dee Fit": dee_fit,
                "Setup": setup,
                "ATR %": round(_f(latest["atr_pct"]), 2),
                "RVOL": round(_f(latest["rvol"]), 2),
                "Distance EMA21 %": round(_f(latest["distance_from_ema21"]), 2),
                "Reasons": reasons,
                "Grade": grade,
                "Momo Score": momo_score,
                "Momo Confidence": confidence["Momo Confidence"],
                "Confidence Rating": confidence["Confidence Rating"],
                "EMA21": round(_f(latest.get("ema21")), 2),
                "EMA50": round(_f(latest.get("ema50")), 2),
                "EMA200": round(_f(latest.get("ema200")), 2),
                "RSI": round(_f(latest.get("rsi14")), 2),
                "MACD": round(_f(latest.get("macd")), 4),
                "MACD Signal": round(_f(latest.get("macd_signal")), 4),
                "MACD Histogram": round(_f(latest.get("macd_hist")), 4),
            }
            for key, value in confidence["Confidence Breakdown"].items():
                row[f"{key} Confidence"] = value
            row.update(levels)
            row.update(risk_reward)
            row.update(targets)
            results.append(row)
        except Exception:
            continue

    preferred = ["Symbol", "Grade", "Momo Score", "Dee Fit", "Score", "Setup", "Close", "ATR %", "RVOL", "Distance EMA21 %", "Reasons"]
    hidden = [
        "__Universe Count", "__Prescreened Count", "__Prescreen Eligible Count", "__Prescreen Bars Count",
        "__Prescreen Strict Count", "__Prescreen Standard Count", "__Prescreen Expanded Count",
        "__Prescreen Request Failures", "__Usable History Count", "Momo Confidence", "Confidence Rating",
        "Trend Confidence", "Location Confidence", "Momentum Confidence", "Volume Confidence", "Opportunity Confidence", "Risk Confidence", "Structure Confidence",
        "EMA21", "EMA50", "EMA200", "RSI", "MACD", "MACD Signal", "MACD Histogram",
        "Support 1", "Support 2", "Support 3", "Resistance 1", "Resistance 2", "Resistance 3",
        "Support 1 Quality", "Support 2 Quality", "Support 3 Quality", "Resistance 1 Quality", "Resistance 2 Quality", "Resistance 3 Quality",
        "Support 1 Touches", "Support 2 Touches", "Support 3 Touches", "Resistance 1 Touches", "Resistance 2 Touches", "Resistance 3 Touches",
        "Reference Entry", "Risk Reference", "Reward Reference", "Risk Per Share", "Reward Per Share", "Risk Reward", "Risk Reward Status",
        "T1", "T1 Upside %", "T1 R", "T2", "T2 Upside %", "T2 R", "T3", "T3 Upside %", "T3 R",
    ]
    all_columns = preferred + hidden
    if not results:
        return pd.DataFrame(columns=all_columns)
    result = pd.DataFrame(results)
    for column in all_columns:
        if column not in result.columns:
            result[column] = pd.NA
    result = result.sort_values(["Dee Fit", "Score"], ascending=[False, False])
    return result[all_columns]

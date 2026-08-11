from __future__ import annotations

import math
import re
from typing import Any
from zoneinfo import ZoneInfo

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


def _live_adjusted_ranking(ranking: pd.DataFrame, live_snapshots: dict[str, dict[str, Any]] | None, candidate_pool: list[str] | None, limit: int = SCAN_LIMIT):
    ranked = ranking.copy()
    if candidate_pool:
        pool = set(candidate_pool)
        ranked = ranked[ranked["Symbol"].isin(pool)].copy()
    live_snapshots = live_snapshots or {}
    if live_snapshots and not ranked.empty:
        def live_score(row):
            snap = live_snapshots.get(str(row["Symbol"]).upper()) or {}
            price = _f(snap.get("close"), _f(row.get("Close")))
            ema21 = _f(row.get("EMA21"))
            ema50 = _f(row.get("EMA50"))
            ema200 = _f(row.get("EMA200"))
            base = _f(row.get("Preliminary Score"))
            if ema21:
                old_distance = _f(row.get("Distance EMA21 %"), 99)
                new_distance = (price - ema21) / ema21 * 100
                # Re-weight location using today's price without double counting the old location score.
                base += max(-16.0, 18.0 - abs(new_distance - 1.5) * 3.0) - max(-16.0, 18.0 - abs(old_distance - 1.5) * 3.0)
                if price > ema21 and _f(row.get("Close")) <= ema21:
                    base += 12
                if price < ema21 and _f(row.get("Close")) > ema21:
                    base -= 8
            if price > ema21 > ema50 > ema200:
                base += 6
            return base
        ranked["Live Preliminary Score"] = ranked.apply(live_score, axis=1)
        ranked = ranked.sort_values(["Live Preliminary Score", "Dollar Volume"], ascending=[False, False])
    else:
        ranked["Live Preliminary Score"] = ranked["Preliminary Score"]
    return ranked.head(limit).copy()


def _session_progress_fraction(asof: Any) -> float | None:
    """Regular-session fraction represented by a current volume observation."""
    if not asof:
        return None
    try:
        stamp = pd.Timestamp(asof)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("UTC")
        eastern = stamp.tz_convert(ZoneInfo("America/New_York"))
        minutes = (eastern.hour * 60 + eastern.minute) - (9 * 60 + 30)
        if minutes <= 0:
            return None
        return max(0.05, min(1.0, minutes / 390.0))
    except Exception:
        return None


def run_scan_v2(
    history: pd.DataFrame | None = None,
    progress_callback=None,
    live_snapshots: dict[str, dict[str, Any]] | None = None,
    candidate_pool: list[str] | None = None,
    ranking_override: pd.DataFrame | None = None,
    diagnostics_override: dict[str, Any] | None = None,
) -> pd.DataFrame:
    if history is None:
        status = history_status()
        if not status["ready"]:
            raise RuntimeError(
                f"Scanner v2 market database is not ready ({status['sessions']}/{MINIMUM_READY_SESSIONS} required sessions)."
            )
        history = load_history()
    if ranking_override is not None and not ranking_override.empty:
        ranking = ranking_override.copy()
        diagnostics = dict(diagnostics_override or {})
        diagnostics.setdefault("universe_count", int(history["symbol"].nunique()))
        diagnostics.setdefault("usable_history_count", int(history.groupby("symbol").size().ge(MINIMUM_DAILY_BARS).sum()))
        diagnostics.setdefault("eligible_count", int(len(ranking)))
        if progress_callback:
            progress_callback("Using cached whole-market strategy ranking", 0.30)
    else:
        if progress_callback:
            progress_callback("Ranking the eligible market", 0.30)
        _symbols, ranking, diagnostics = rank_universe(history, max(SCAN_LIMIT, len(candidate_pool or [])))
    current_ranking = _live_adjusted_ranking(ranking, live_snapshots, candidate_pool, SCAN_LIMIT)
    symbols = current_ranking["Symbol"].astype(str).tolist()
    diagnostics["selected_count"] = len(symbols)
    if progress_callback:
        progress_callback(f"Running full MomoPro analysis on {len(symbols)} current strategy-ranked stocks", 0.45)
    ranking_map = current_ranking.set_index("Symbol").to_dict(orient="index")
    groups = {symbol: frame.sort_values("date") for symbol, frame in history[history["symbol"].isin(symbols)].groupby("symbol", sort=False)}
    results = []
    analysis_failures = 0
    first_analysis_error = ""

    total_symbols = max(1, len(symbols))
    for symbol_index, symbol in enumerate(symbols, start=1):
        if progress_callback and (symbol_index == 1 or symbol_index % 25 == 0):
            progress_callback(f"Full MomoPro analysis {symbol_index}/{total_symbols}", 0.45 + 0.50 * (symbol_index / total_symbols))
        try:
            raw = groups.get(symbol)
            if raw is None or len(raw) < MINIMUM_DAILY_BARS:
                continue
            symbol_df = raw.rename(columns={"date": "timestamp"}).copy()
            symbol_df["timestamp"] = pd.to_datetime(symbol_df["timestamp"])
            snap = (live_snapshots or {}).get(symbol) or {}
            current_session_rvol = None
            if snap:
                avg20 = _f(pd.to_numeric(symbol_df["volume"], errors="coerce").tail(20).mean(), 0.0)
                current_price = _f(snap.get("close"), _f(symbol_df.iloc[-1]["close"]))
                current_volume = _f(snap.get("volume"), 0.0)
                progress_fraction = _session_progress_fraction(snap.get("volume_asof") or snap.get("asof"))

                if current_volume > 0 and avg20 > 0 and progress_fraction:
                    expected_so_far = avg20 * progress_fraction
                    if expected_so_far > 0:
                        current_session_rvol = current_volume / expected_so_far

                # Durable Massive history stores session dates without timezone
                # information. Keep the synthetic current-session date equally
                # tz-naive so the comparison cannot raise:
                #   TypeError: Cannot compare tz-naive and tz-aware timestamps.
                current_session_date = (
                    pd.Timestamp.now(tz="America/New_York")
                    .normalize()
                    .tz_localize(None)
                )
                synthetic = {
                    "timestamp": current_session_date,
                    "open": _f(snap.get("open"), current_price),
                    "high": max(_f(snap.get("high"), current_price), current_price),
                    "low": min(_f(snap.get("low"), current_price), current_price),
                    "close": current_price,
                    "volume": current_volume if current_volume > 0 else (avg20 if avg20 > 0 else _f(symbol_df.iloc[-1].get("volume"), 0.0)),
                }

                last_session_date = pd.Timestamp(symbol_df["timestamp"].max()).normalize()
                if last_session_date.tzinfo is not None:
                    last_session_date = last_session_date.tz_localize(None)

                if last_session_date < current_session_date:
                    symbol_df = pd.concat([symbol_df, pd.DataFrame([synthetic])], ignore_index=True)
                else:
                    for col, value in synthetic.items():
                        if col != "timestamp":
                            symbol_df.loc[symbol_df.index[-1], col] = value
            symbol_df = calculate_indicators(symbol_df)
            latest, previous = symbol_df.iloc[-1], symbol_df.iloc[-2]
            pre = ranking_map.get(symbol, {})
            if current_session_rvol is not None:
                latest = latest.copy()
                latest["rvol"] = current_session_rvol
            elif pre.get("RVOL") is not None:
                latest = latest.copy()
                latest["rvol"] = _f(pre.get("RVOL"), _f(latest.get("rvol")))
            required = [latest.get("ema200"), latest.get("rsi14"), latest.get("macd_hist"), latest.get("atr_pct"), latest.get("rvol"), latest.get("prior_120_high")]
            if any(pd.isna(value) for value in required):
                continue
            levels = calculate_levels(symbol_df)
            risk_reward = calculate_risk_reward(latest["close"], levels)
            targets = calculate_targets(entry=risk_reward["Reference Entry"], risk_per_share=risk_reward["Risk Per Share"], levels=levels)
            score, dee_fit, momo_score, modules, grade, setup, reasons = score_stock(latest, previous)
            confidence = calculate_confidence(modules=modules, risk_reward_data=risk_reward, levels=levels)
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
                "__Scan As Of": snap.get("asof") if snap else None,
                "__Price Feed": snap.get("price_feed") if snap else "Completed EOD",
                "__Volume Feed": snap.get("volume_feed") if snap else "Completed EOD",
            }
            for key, value in confidence["Confidence Breakdown"].items():
                row[f"{key} Confidence"] = value
            row.update(levels)
            row.update(risk_reward)
            row.update(targets)
            results.append(row)
        except Exception as exc:
            analysis_failures += 1
            if not first_analysis_error:
                first_analysis_error = f"{type(exc).__name__}: {exc}"
            continue

    preferred = ["Symbol", "Grade", "Momo Score", "Dee Fit", "Score", "Setup", "Close", "ATR %", "RVOL", "Distance EMA21 %", "Reasons"]
    hidden = [
        "__Universe Count", "__Prescreened Count", "__Prescreen Eligible Count", "__Prescreen Bars Count",
        "__Prescreen Strict Count", "__Prescreen Standard Count", "__Prescreen Expanded Count",
        "__Prescreen Request Failures", "__Usable History Count", "Momo Confidence", "Confidence Rating",
        "Trend Confidence", "Location Confidence", "Momentum Confidence", "Volume Confidence", "Opportunity Confidence", "Risk Confidence", "Structure Confidence",
        "EMA21", "EMA50", "EMA200", "RSI", "MACD", "MACD Signal", "MACD Histogram", "__Scan As Of", "__Price Feed", "__Volume Feed", "__Analysis Failures", "__First Analysis Error",
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
    if progress_callback:
        progress_callback("Final candidates ready", 1.0)
    return result[all_columns]

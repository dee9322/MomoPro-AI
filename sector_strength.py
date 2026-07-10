from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


SECTOR_ETFS = {
    "XLK": "Technology",
    "XLC": "Communication Services",
    "XLY": "Consumer Discretionary",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLE": "Energy",
    "XLV": "Health Care",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
}

RISK_ON_SECTORS = {"XLK", "XLC", "XLY", "XLF", "XLI", "XLB", "XLE"}
DEFENSIVE_SECTORS = {"XLV", "XLP", "XLU", "XLRE"}
HISTORY_DAYS = 350
MINIMUM_BARS = 220


def _pct_change(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods:
        return None

    earlier = float(series.iloc[-(periods + 1)])
    latest = float(series.iloc[-1])

    if earlier == 0:
        return None

    return ((latest / earlier) - 1) * 100


def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def _analyze_sector(
    df: pd.DataFrame,
    symbol: str,
    name: str,
    spy_returns: dict[str, float | None],
) -> dict[str, Any]:
    if df is None or len(df) < MINIMUM_BARS:
        return {
            "symbol": symbol,
            "sector": name,
            "status": "Unavailable",
            "score": None,
            "trend": "Unavailable",
            "rotation": "Unavailable",
        }

    data = df.copy()
    data["ema21"] = data["close"].ewm(span=21, adjust=False).mean()
    data["ema50"] = data["close"].ewm(span=50, adjust=False).mean()
    data["ema200"] = data["close"].ewm(span=200, adjust=False).mean()
    data["rsi14"] = _calculate_rsi(data["close"])

    ema12 = data["close"].ewm(span=12, adjust=False).mean()
    ema26 = data["close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    data["macd_hist"] = macd - signal

    latest = data.iloc[-1]
    previous = data.iloc[-2]

    close = float(latest["close"])
    ema21 = float(latest["ema21"])
    ema50 = float(latest["ema50"])
    ema200 = float(latest["ema200"])
    rsi14 = float(latest["rsi14"])
    macd_hist = float(latest["macd_hist"])
    previous_macd_hist = float(previous["macd_hist"])

    ret_5d = _pct_change(data["close"], 5)
    ret_20d = _pct_change(data["close"], 20)
    ret_60d = _pct_change(data["close"], 60)

    rs_5d = (
        ret_5d - spy_returns.get("5d")
        if ret_5d is not None and spy_returns.get("5d") is not None
        else None
    )
    rs_20d = (
        ret_20d - spy_returns.get("20d")
        if ret_20d is not None and spy_returns.get("20d") is not None
        else None
    )
    rs_60d = (
        ret_60d - spy_returns.get("60d")
        if ret_60d is not None and spy_returns.get("60d") is not None
        else None
    )

    score = 0
    score += 15 if close > ema21 else 0
    score += 15 if close > ema50 else 0
    score += 15 if close > ema200 else 0
    score += 15 if ema21 > ema50 > ema200 else 0
    score += 10 if ema21 > float(previous["ema21"]) else 0
    score += 10 if macd_hist > 0 else 0
    score += 5 if macd_hist > previous_macd_hist else 0

    if 50 <= rsi14 <= 70:
        score += 10
    elif rsi14 < 40:
        score -= 10
    elif rsi14 > 75:
        score -= 5

    if rs_20d is not None:
        if rs_20d >= 5:
            score += 15
        elif rs_20d >= 2:
            score += 10
        elif rs_20d > 0:
            score += 5
        elif rs_20d <= -5:
            score -= 10

    score = max(0, min(round(score), 100))

    if score >= 80:
        trend = "Leading"
    elif score >= 65:
        trend = "Strong"
    elif score >= 45:
        trend = "Mixed"
    elif score >= 25:
        trend = "Weak"
    else:
        trend = "Lagging"

    short_rs = rs_5d if rs_5d is not None else 0
    medium_rs = rs_20d if rs_20d is not None else 0

    if short_rs >= medium_rs + 1.5:
        rotation = "Improving"
    elif short_rs <= medium_rs - 1.5:
        rotation = "Weakening"
    elif medium_rs > 0:
        rotation = "Holding Leadership"
    elif medium_rs < 0:
        rotation = "Holding Weakness"
    else:
        rotation = "Stable"

    return {
        "symbol": symbol,
        "sector": name,
        "status": "Available",
        "close": round(close, 2),
        "score": score,
        "trend": trend,
        "rotation": rotation,
        "rsi14": round(rsi14, 1),
        "return_5d_pct": round(ret_5d, 2) if ret_5d is not None else None,
        "return_20d_pct": round(ret_20d, 2) if ret_20d is not None else None,
        "return_60d_pct": round(ret_60d, 2) if ret_60d is not None else None,
        "relative_5d_vs_spy": round(rs_5d, 2) if rs_5d is not None else None,
        "relative_20d_vs_spy": round(rs_20d, 2) if rs_20d is not None else None,
        "relative_60d_vs_spy": round(rs_60d, 2) if rs_60d is not None else None,
        "above_ema21": close > ema21,
        "above_ema50": close > ema50,
        "above_ema200": close > ema200,
    }


def get_sector_strength(api_key: str, secret_key: str) -> dict[str, Any]:
    symbols = ["SPY", *SECTOR_ETFS.keys()]

    try:
        client = StockHistoricalDataClient(api_key, secret_key)
        end = datetime.now()
        start = end - timedelta(days=HISTORY_DAYS)

        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )

        bars = client.get_stock_bars(request).df

        if bars.empty:
            raise RuntimeError("No sector data was returned.")

        all_bars = bars.reset_index()
        spy_df = all_bars[all_bars["symbol"] == "SPY"].copy()

        if len(spy_df) < MINIMUM_BARS:
            raise RuntimeError("Not enough SPY history for sector comparison.")

        spy_returns = {
            "5d": _pct_change(spy_df["close"], 5),
            "20d": _pct_change(spy_df["close"], 20),
            "60d": _pct_change(spy_df["close"], 60),
        }

        sectors = []
        for symbol, name in SECTOR_ETFS.items():
            sector_df = all_bars[all_bars["symbol"] == symbol].copy()
            sectors.append(
                _analyze_sector(
                    sector_df,
                    symbol,
                    name,
                    spy_returns,
                )
            )

        available = [item for item in sectors if item.get("score") is not None]
        ranked = sorted(available, key=lambda item: item["score"], reverse=True)

        leaders = ranked[:3]
        laggards = sorted(available, key=lambda item: item["score"])[:3]
        improving = [item for item in ranked if item.get("rotation") == "Improving"]
        weakening = [item for item in ranked if item.get("rotation") == "Weakening"]

        risk_on_scores = [
            item["score"] for item in available if item["symbol"] in RISK_ON_SECTORS
        ]
        defensive_scores = [
            item["score"] for item in available if item["symbol"] in DEFENSIVE_SECTORS
        ]

        risk_on_average = (
            sum(risk_on_scores) / len(risk_on_scores) if risk_on_scores else 50
        )
        defensive_average = (
            sum(defensive_scores) / len(defensive_scores)
            if defensive_scores
            else 50
        )

        rotation_gap = risk_on_average - defensive_average

        if rotation_gap >= 8:
            rotation_regime = "Risk-On Rotation"
        elif rotation_gap <= -8:
            rotation_regime = "Defensive Rotation"
        else:
            rotation_regime = "Balanced Rotation"

        leader_names = ", ".join(item["sector"] for item in leaders) or "none"
        laggard_names = ", ".join(item["sector"] for item in laggards) or "none"

        summary = (
            f"{rotation_regime}. Leading sectors are {leader_names}. "
            f"The weakest groups are {laggard_names}."
        )

        overall_score = (
            round(sum(item["score"] for item in available) / len(available))
            if available
            else None
        )

        return {
            "status": "Available",
            "sector_score": overall_score,
            "rotation_regime": rotation_regime,
            "risk_on_average": round(risk_on_average, 1),
            "defensive_average": round(defensive_average, 1),
            "leaders": leaders,
            "laggards": laggards,
            "improving": improving[:5],
            "weakening": weakening[:5],
            "rankings": ranked,
            "summary": summary,
            "benchmark": "SPY",
        }

    except Exception as error:
        return {
            "status": f"Unavailable: {error}",
            "sector_score": None,
            "rotation_regime": "Unavailable",
            "risk_on_average": None,
            "defensive_average": None,
            "leaders": [],
            "laggards": [],
            "improving": [],
            "weakening": [],
            "rankings": [],
            "summary": "Sector strength could not be calculated.",
            "benchmark": "SPY",
        }

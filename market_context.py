from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from market_breadth import get_market_breadth
from market_sentiment import get_market_sentiment
from sector_strength import get_sector_strength


MARKET_SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "VIXY"]
MARKET_WEIGHTS = {
    "SPY": 0.30,
    "QQQ": 0.35,
    "IWM": 0.20,
    "DIA": 0.15,
}
HISTORY_DAYS = 350
MINIMUM_BARS = 220


def _empty_index(symbol: str, label: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "label": label,
        "close": None,
        "ema21": None,
        "ema50": None,
        "ema200": None,
        "rsi14": None,
        "macd_hist": None,
        "trend": "Unavailable",
        "score": None,
        "above_ema21": None,
        "above_ema50": None,
        "above_ema200": None,
        "ema_stack_bullish": None,
    }


def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def _analyze_symbol(df: pd.DataFrame, symbol: str, label: str) -> dict[str, Any]:
    if df is None or len(df) < MINIMUM_BARS:
        return _empty_index(symbol, label)

    data = df.copy()
    data["ema21"] = data["close"].ewm(span=21, adjust=False).mean()
    data["ema50"] = data["close"].ewm(span=50, adjust=False).mean()
    data["ema200"] = data["close"].ewm(span=200, adjust=False).mean()
    data["rsi14"] = _calculate_rsi(data["close"])

    ema12 = data["close"].ewm(span=12, adjust=False).mean()
    ema26 = data["close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    data["macd_hist"] = macd - macd_signal

    latest = data.iloc[-1]
    previous = data.iloc[-2]

    close = float(latest["close"])
    ema21 = float(latest["ema21"])
    ema50 = float(latest["ema50"])
    ema200 = float(latest["ema200"])
    rsi14 = float(latest["rsi14"])
    macd_hist = float(latest["macd_hist"])
    previous_macd_hist = float(previous["macd_hist"])

    above_ema21 = close > ema21
    above_ema50 = close > ema50
    above_ema200 = close > ema200
    ema_stack_bullish = ema21 > ema50 > ema200
    ema21_rising = ema21 > float(previous["ema21"])
    macd_improving = macd_hist > previous_macd_hist

    score = 0
    score += 20 if above_ema21 else 0
    score += 20 if above_ema50 else 0
    score += 20 if above_ema200 else 0
    score += 15 if ema_stack_bullish else 0
    score += 10 if ema21_rising else 0
    score += 10 if macd_hist > 0 else 0
    score += 5 if macd_improving else 0

    if 50 <= rsi14 <= 70:
        score += 10
    elif rsi14 < 40:
        score -= 10
    elif rsi14 > 75:
        score -= 5

    score = max(0, min(round(score), 100))

    if score >= 80:
        trend = "Bullish"
    elif score >= 60:
        trend = "Constructive"
    elif score >= 40:
        trend = "Mixed"
    elif score >= 20:
        trend = "Weak"
    else:
        trend = "Bearish"

    return {
        "symbol": symbol,
        "label": label,
        "close": round(close, 2),
        "ema21": round(ema21, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "rsi14": round(rsi14, 1),
        "macd_hist": round(macd_hist, 4),
        "trend": trend,
        "score": score,
        "above_ema21": above_ema21,
        "above_ema50": above_ema50,
        "above_ema200": above_ema200,
        "ema_stack_bullish": ema_stack_bullish,
    }


def _build_summary(indexes: dict[str, dict[str, Any]], vix_proxy: dict[str, Any]) -> str:
    bullish = [
        symbol
        for symbol in ("SPY", "QQQ", "IWM", "DIA")
        if indexes.get(symbol, {}).get("trend") in {"Bullish", "Constructive"}
    ]
    weak = [
        symbol
        for symbol in ("SPY", "QQQ", "IWM", "DIA")
        if indexes.get(symbol, {}).get("trend") in {"Weak", "Bearish"}
    ]

    if len(bullish) >= 3:
        first = "Broad equity conditions are constructive."
    elif len(weak) >= 3:
        first = "Broad equity conditions are defensive."
    else:
        first = "Broad equity conditions are mixed."

    qqq_trend = indexes.get("QQQ", {}).get("trend", "Unavailable")
    spy_trend = indexes.get("SPY", {}).get("trend", "Unavailable")
    vix_trend = vix_proxy.get("trend", "Unavailable")

    return (
        f"{first} SPY is {spy_trend.lower()}, QQQ is {qqq_trend.lower()}, "
        f"and the VIXY volatility proxy is {vix_trend.lower()}."
    )


def get_market_context(api_key: str, secret_key: str) -> dict[str, Any]:
    """
    Analyze SPY, QQQ, IWM, DIA, and VIXY once per scan.

    VIXY is used as a volatility-market proxy because Alpaca's stock feed does
    not provide the cash VIX index directly. Later sentiment integrations can
    replace or supplement this proxy with a direct VIX source.
    """
    labels = {
        "SPY": "S&P 500",
        "QQQ": "Nasdaq 100",
        "IWM": "Russell 2000",
        "DIA": "Dow Jones",
        "VIXY": "VIX proxy",
    }

    breadth = get_market_breadth(api_key, secret_key)
    sectors = get_sector_strength(api_key, secret_key)

    try:
        client = StockHistoricalDataClient(api_key, secret_key)
        end = datetime.now()
        start = end - timedelta(days=HISTORY_DAYS)

        request = StockBarsRequest(
            symbol_or_symbols=MARKET_SYMBOLS,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX,
        )

        bars = client.get_stock_bars(request).df

        if bars.empty:
            raise RuntimeError("No market-context bars were returned.")

        all_bars = bars.reset_index()
        indexes: dict[str, dict[str, Any]] = {}

        for symbol in MARKET_SYMBOLS:
            symbol_df = all_bars[all_bars["symbol"] == symbol].copy()
            indexes[symbol] = _analyze_symbol(
                symbol_df,
                symbol,
                labels[symbol],
            )

        available_scores = [
            indexes[symbol]["score"] * MARKET_WEIGHTS[symbol]
            for symbol in MARKET_WEIGHTS
            if indexes[symbol]["score"] is not None
        ]
        available_weight = sum(
            MARKET_WEIGHTS[symbol]
            for symbol in MARKET_WEIGHTS
            if indexes[symbol]["score"] is not None
        )

        base_score = (
            sum(available_scores) / available_weight
            if available_weight
            else 50
        )

        vix_proxy = indexes["VIXY"]
        vix_modifier = 0

        if vix_proxy["score"] is not None:
            if vix_proxy["trend"] in {"Bullish", "Constructive"}:
                vix_modifier = -10
            elif vix_proxy["trend"] in {"Weak", "Bearish"}:
                vix_modifier = 8

        market_score = round(max(0, min(base_score + vix_modifier, 100)))

        sentiment = get_market_sentiment(
            market_score=market_score,
            breadth=breadth,
            indexes=indexes,
        )

        if market_score >= 75:
            market_trend = "Bullish"
            risk_environment = "Risk On"
        elif market_score >= 58:
            market_trend = "Constructive"
            risk_environment = "Moderately Risk On"
        elif market_score >= 42:
            market_trend = "Mixed"
            risk_environment = "Neutral"
        elif market_score >= 25:
            market_trend = "Weak"
            risk_environment = "Moderately Risk Off"
        else:
            market_trend = "Bearish"
            risk_environment = "Risk Off"

        return {
            "market_score": market_score,
            "market_trend": market_trend,
            "risk_environment": risk_environment,
            "summary": _build_summary(indexes, vix_proxy),
            "indexes": indexes,
            "vix_source": "VIXY volatility proxy",
            "breadth": breadth,
            "sentiment": sentiment,
            "sectors": sectors,
            "status": "Available",
        }

    except Exception as error:
        indexes = {
            symbol: _empty_index(symbol, labels[symbol])
            for symbol in MARKET_SYMBOLS
        }

        return {
            "market_score": None,
            "market_trend": "Unavailable",
            "risk_environment": "Unavailable",
            "summary": "Market context could not be calculated for this scan.",
            "indexes": indexes,
            "vix_source": "VIXY volatility proxy",
            "breadth": breadth,
            "sentiment": {
                "status": "Unavailable",
                "fear_greed_score": None,
                "fear_greed_label": "Unavailable",
                "risk_appetite": "Unavailable",
                "total_put_call_ratio": None,
                "equity_put_call_ratio": None,
                "put_call_signal": "Unavailable",
                "summary": "Market sentiment could not be calculated.",
                "warning": None,
                "source": "Cboe Daily Market Statistics + Momo composite",
            },
            "sectors": sectors,
            "status": f"Unavailable: {error}",
        }

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from market_universe import get_market_universe


def calculate_indicators(df):
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

    df["prev_close"] = df["close"].shift(1)
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df["high"] - df["prev_close"]),
            abs(df["low"] - df["prev_close"])
        )
    )

    df["atr14"] = df["tr"].rolling(14).mean()
    df["atr_pct"] = (df["atr14"] / df["close"]) * 100
    df["avg_volume20"] = df["volume"].rolling(20).mean()
    df["rvol"] = df["volume"] / df["avg_volume20"]
    df["distance_from_ema21"] = ((df["close"] - df["ema21"]) / df["ema21"]) * 100

    return df


def score_stock(latest, previous):
    score = 0
    reasons = []

    price = latest["close"]

    if 3 <= price <= 50:
        score += 10
        reasons.append("Price in preferred range")

    if latest["volume"] >= 1_000_000:
        score += 10
        reasons.append("Strong liquidity")

    if latest["close"] > latest["ema21"]:
        score += 20
        reasons.append("Above EMA21")

    if previous["close"] < previous["ema21"] and latest["close"] > latest["ema21"]:
        score += 20
        reasons.append("Fresh EMA21 reclaim")

    if latest["close"] > latest["ema50"]:
        score += 15
        reasons.append("Above EMA50")

    if latest["atr_pct"] >= 4:
        score += 10
        reasons.append("Good ATR movement potential")

    if latest["rvol"] >= 1.5:
        score += 10
        reasons.append("Relative volume elevated")

    if 0 <= latest["distance_from_ema21"] <= 6:
        score += 15
        reasons.append("Not too extended from EMA21")

    return min(score, 100), ", ".join(reasons)


def run_scan():
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_SECRET_KEY"]

    client = StockHistoricalDataClient(api_key, secret_key)

    end = datetime.now()
    start = end - timedelta(days=120)

        results = []

    symbols = get_market_universe(limit=500)

    for symbol in symbols:
        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed=DataFeed.IEX
            )

            bars = client.get_stock_bars(request).df

            if bars.empty:
                continue

            df = bars.reset_index()
            df = df[df["symbol"] == symbol].copy()

            if len(df) < 60:
                continue

            df = calculate_indicators(df)

            latest = df.iloc[-1]
            previous = df.iloc[-2]

            score, reasons = score_stock(latest, previous)

            results.append({
                "Symbol": symbol,
                "Close": round(latest["close"], 2),
                "Score": score,
                "ATR %": round(latest["atr_pct"], 2),
                "RVOL": round(latest["rvol"], 2),
                "Distance EMA21 %": round(latest["distance_from_ema21"], 2),
                "Reasons": reasons
            })

        except Exception as e:
            results.append({
                "Symbol": symbol,
                "Close": None,
                "Score": 0,
                "ATR %": None,
                "RVOL": None,
                "Distance EMA21 %": None,
                "Reasons": f"Error: {e}"
            })

    return pd.DataFrame(results).sort_values("Score", ascending=False)

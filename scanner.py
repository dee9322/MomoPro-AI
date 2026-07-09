import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from market_universe import get_market_universe
from pre_screener import select_best_symbols
from indicators import calculate_indicators
from scoring import score_stock






def run_scan():
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_SECRET_KEY"]

    client = StockHistoricalDataClient(api_key, secret_key)

    end = datetime.now()
    start = end - timedelta(days=120)

    results = []

    all_symbols = get_market_universe(limit=None)
    symbols = select_best_symbols(api_key, secret_key, all_symbols, limit=500)

    chunk_size = 100

    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i:i + chunk_size]

        try:
            request = StockBarsRequest(
                symbol_or_symbols=chunk,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed=DataFeed.IEX
            )

            bars = client.get_stock_bars(request).df

            if bars.empty:
                continue

            all_bars = bars.reset_index()

            for symbol in chunk:
                try:
                    df = all_bars[all_bars["symbol"] == symbol].copy()

                    if len(df) < 60:
                        continue

                    df = calculate_indicators(df)

                    latest = df.iloc[-1]
                    previous = df.iloc[-2]

                    score, dee_fit, momo_score, grade, setup, reasons = score_stock(latest, previous)

                    results.append({
                        "Symbol": symbol,
                        "Close": round(latest["close"], 2),
                        "Score": score,
                        "Dee Fit": dee_fit,
                        "Setup": setup,
                        "ATR %": round(latest["atr_pct"], 2),
                        "RVOL": round(latest["rvol"], 2),
                        "Distance EMA21 %": round(latest["distance_from_ema21"], 2),
                        "Reasons": reasons,
                        "Grade": grade,
                        "Momo Score": momo_score,
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

        except Exception:
            continue

    df = pd.DataFrame(results)

    df = df.sort_values(
        ["Dee Fit", "Score"],
        ascending=[False, False]
    )

    preferred_columns = [
        "Symbol",
        "Grade",
        "Momo Score",
        "Dee Fit",
        "Score",
        "Setup",
        "Close",
        "ATR %",
        "RVOL",
        "Distance EMA21 %",
        "Reasons"
    ]

    return df[preferred_columns]

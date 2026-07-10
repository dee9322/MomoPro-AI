from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from indicators import calculate_indicators
from levels import calculate_levels
from market_universe import get_market_universe
from pre_screener import select_best_symbols
from scoring import score_stock


HISTORY_CALENDAR_DAYS = 420
MINIMUM_DAILY_BARS = 220
SCAN_LIMIT = 500
CHUNK_SIZE = 100


def run_scan():
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_SECRET_KEY"]

    client = StockHistoricalDataClient(api_key, secret_key)

    end = datetime.now()
    start = end - timedelta(days=HISTORY_CALENDAR_DAYS)

    results = []

    all_symbols = get_market_universe(limit=None)
    symbols = select_best_symbols(
        api_key,
        secret_key,
        all_symbols,
        limit=SCAN_LIMIT,
    )

    for i in range(0, len(symbols), CHUNK_SIZE):
        chunk = symbols[i : i + CHUNK_SIZE]

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

            all_bars = bars.reset_index()

            for symbol in chunk:
                try:
                    df = all_bars[all_bars["symbol"] == symbol].copy()

                    if len(df) < MINIMUM_DAILY_BARS:
                        continue

                    df = calculate_indicators(df)

                    latest = df.iloc[-1]
                    previous = df.iloc[-2]

                    required_values = [
                        latest.get("ema200"),
                        latest.get("rsi14"),
                        latest.get("macd_hist"),
                        latest.get("atr_pct"),
                        latest.get("rvol"),
                        latest.get("prior_120_high"),
                    ]

                    if any(pd.isna(value) for value in required_values):
                        continue

                    levels = calculate_levels(latest)

                    (
                        score,
                        dee_fit,
                        momo_score,
                        grade,
                        setup,
                        reasons,
                    ) = score_stock(latest, previous)

                    results.append(
                        {
                            "Symbol": symbol,
                            "Close": round(float(latest["close"]), 2),
                            "Score": score,
                            "Dee Fit": dee_fit,
                            "Setup": setup,
                            "ATR %": round(float(latest["atr_pct"]), 2),
                            "RVOL": round(float(latest["rvol"]), 2),
                            "Distance EMA21 %": round(
                                float(latest["distance_from_ema21"]),
                                2,
                            ),
                            "Reasons": reasons,
                            "Grade": grade,
                            "Momo Score": momo_score,
                            "Support 1": levels["Support 1"],
                            "Support 2": levels["Support 2"],
                            "Support 3": levels["Support 3"],
                            "Resistance 1": levels["Resistance 1"],
                            "Resistance 2": levels["Resistance 2"],
                            "Resistance 3": levels["Resistance 3"],
                        }
                    )

                except Exception:
                    continue

        except Exception:
            continue

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
        "Reasons",
    ]

    hidden_report_columns = [
        "Support 1",
        "Support 2",
        "Support 3",
        "Resistance 1",
        "Resistance 2",
        "Resistance 3",
    ]

    if not results:
        return pd.DataFrame(
            columns=preferred_columns + hidden_report_columns
        )

    df = pd.DataFrame(results)

    df = df.sort_values(
        ["Dee Fit", "Score"],
        ascending=[False, False],
    )

    return df[preferred_columns + hidden_report_columns]

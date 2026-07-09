import pandas as pd
from datetime import datetime, timedelta

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed


def select_best_symbols(api_key, secret_key, symbols, limit=500):
    client = StockHistoricalDataClient(api_key, secret_key)

    end = datetime.now()
    start = end - timedelta(days=45)

    rows = []
    chunk_size = 200

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

            df = bars.reset_index()

            for symbol in chunk:
                sdf = df[df["symbol"] == symbol].copy()

                if len(sdf) < 20:
                    continue

                latest = sdf.iloc[-1]
                previous = sdf.iloc[-2]

                close = latest["close"]
                volume = latest["volume"]
                avg_volume = sdf["volume"].tail(20).mean()
                rvol = volume / avg_volume if avg_volume else 0
                pct_change = ((latest["close"] - previous["close"]) / previous["close"]) * 100
                dollar_volume = close * volume

                if close < 3 or close > 50:
                    continue
                if avg_volume < 500_000:
                    continue
                if dollar_volume < 5_000_000:
                    continue
                    
                activity_score = (
                    dollar_volume / 1_000_000
                    + abs(pct_change) * 5
                    + rvol * 10
                )

                rows.append({
                    "Symbol": symbol,
                    "Activity Score": activity_score,
                    "Close": close,
                    "Volume": volume,
                    "Dollar Volume": dollar_volume,
                    "RVOL": rvol,
                    "% Change": pct_change
                })

        except Exception:
            continue

    ranked = pd.DataFrame(rows)

    if ranked.empty:
        return symbols[:limit]

    ranked = ranked.sort_values(
        by=["Activity Score", "Dollar Volume", "RVOL", "% Change"],
        ascending=[False, False, False, False]
    )

    return ranked.head(limit)["Symbol"].tolist()

import pandas as pd


def select_best_symbols_from_results(results, limit=500):
    df = pd.DataFrame(results)

    if df.empty:
        return df

    df = df.dropna(subset=["Close", "Score", "ATR %", "RVOL"])

    df["Activity Score"] = (
        df["Score"] * 1.0 +
        df["RVOL"] * 8.0 +
        df["ATR %"] * 2.0
    )

    df = df.sort_values(
        by=["Activity Score", "Score", "RVOL", "ATR %"],
        ascending=[False, False, False, False]
    )

    if limit:
        df = df.head(limit)

    return df

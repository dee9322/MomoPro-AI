import numpy as np


def calculate_indicators(df):
    df = df.copy()

    # EMAs
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

    # ATR
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

    # Volume / RVOL
    df["avg_volume20"] = df["volume"].rolling(20).mean()
    df["rvol"] = df["volume"] / df["avg_volume20"]

    # EMA21 distance
    df["distance_from_ema21"] = ((df["close"] - df["ema21"]) / df["ema21"]) * 100

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["rsi14"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    df["prior_60_high"] = df["high"].rolling(60).max().shift(1)
    df["room_to_high_pct"] = ((df["prior_60_high"] - df["close"]) / df["close"]) * 100

    return df

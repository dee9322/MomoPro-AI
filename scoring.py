def score_stock(latest, previous):
    score = 0
    reasons = []

    price = latest["close"]
    distance = latest["distance_from_ema21"]
    rvol = latest["rvol"]
    atr_pct = latest["atr_pct"]
    rsi = latest["rsi14"]
    macd_hist = latest["macd_hist"]
    prev_macd_hist = previous["macd_hist"]

    # Price filter
    if 3 <= price <= 50:
        score += 8
        reasons.append("Price in preferred range")
    elif price < 3:
        score -= 10
        reasons.append("Under preferred price range")

    # Trend structure
    if latest["close"] > latest["ema21"]:
        score += 10
        reasons.append("Above EMA21")

    if latest["ema21"] > latest["ema50"]:
        score += 10
        reasons.append("EMA21 above EMA50")

    if latest["close"] > latest["ema200"]:
        score += 8
        reasons.append("Above EMA200")

    # Fresh EMA21 reclaim
    if previous["close"] < previous["ema21"] and latest["close"] > latest["ema21"]:
        score += 22
        reasons.append("Fresh EMA21 reclaim")

    # Entry location - this is your biggest filter
    if distance < 0:
        score -= 15
        reasons.append("Below EMA21")

    elif 0 <= distance <= 2:
        score += 25
        reasons.append("Ideal EMA21 entry location")

    elif 2 < distance <= 4:
        score += 15
        reasons.append("Acceptable EMA21 location")

    elif 4 < distance <= 6:
        score += 4
        reasons.append("Getting extended from EMA21")

    elif distance > 6:
        score -= 20
        reasons.append("Too extended for preferred entry")

    # Volume
    if rvol >= 2:
        score += 14
        reasons.append("Strong relative volume")
    elif rvol >= 1.5:
        score += 10
        reasons.append("Good relative volume")
    elif rvol >= 1:
        score += 4
        reasons.append("Decent relative volume")
    elif rvol < 0.7:
        score -= 8
        reasons.append("Weak relative volume")

    # ATR movement potential
    if 4 <= atr_pct <= 12:
        score += 10
        reasons.append("Good swing range")
    elif atr_pct > 18:
        score -= 6
        reasons.append("Very high volatility risk")

    # RSI
    if 45 <= rsi <= 62:
        score += 10
        reasons.append("Healthy RSI with room")
    elif 62 < rsi <= 70:
        score += 3
        reasons.append("RSI strong but getting warm")
    elif rsi > 70:
        score -= 10
        reasons.append("RSI overextended")

    # MACD
    if macd_hist > prev_macd_hist and macd_hist > 0:
        score += 10
        reasons.append("MACD bullish and improving")
    elif macd_hist > prev_macd_hist:
        score += 5
        reasons.append("MACD improving early")
    elif macd_hist < prev_macd_hist:
        score -= 5
        reasons.append("MACD losing momentum")

    score = max(0, min(score, 100))

    return score, ", ".join(reasons)

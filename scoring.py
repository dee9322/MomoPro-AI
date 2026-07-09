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

    if 3 <= price <= 50:
        score += 10
        reasons.append("Price in preferred range")

    if latest["close"] > latest["ema21"]:
        score += 15
        reasons.append("Above EMA21")

    if latest["close"] > latest["ema50"]:
        score += 10
        reasons.append("Above EMA50")

    if latest["close"] > latest["ema200"]:
        score += 10
        reasons.append("Above EMA200")

    if previous["close"] < previous["ema21"] and latest["close"] > latest["ema21"]:
        score += 20
        reasons.append("Fresh EMA21 reclaim")

    if 0 <= distance <= 2:
        score += 20
        reasons.append("Excellent EMA21 location")
    elif 2 < distance <= 4:
        score += 15
        reasons.append("Good EMA21 location")
    elif 4 < distance <= 6:
        score += 8
        reasons.append("Slightly extended from EMA21")
    elif distance > 8:
        score -= 10
        reasons.append("Too extended from EMA21")

    if rvol >= 2:
        score += 15
        reasons.append("Strong relative volume")
    elif rvol >= 1.5:
        score += 10
        reasons.append("Good relative volume")
    elif rvol >= 1:
        score += 5
        reasons.append("Decent relative volume")

    if atr_pct >= 4:
        score += 10
        reasons.append("Good ATR movement potential")

    if 45 <= rsi <= 65:
        score += 10
        reasons.append("Healthy RSI range")
    elif rsi > 75:
        score -= 8
        reasons.append("RSI overextended")

    if macd_hist > prev_macd_hist:
        score += 10
        reasons.append("MACD momentum improving")

    score = max(0, min(score, 100))

    return score, ", ".join(reasons)

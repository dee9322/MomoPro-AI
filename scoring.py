def score_stock(latest, previous):
    score = 0
    dee_fit = 0
    reasons = []
    setup = "Watchlist"

    price = latest["close"]
    distance = latest["distance_from_ema21"]
    rvol = latest["rvol"]
    atr_pct = latest["atr_pct"]
    rsi = latest["rsi14"]
    macd_hist = latest["macd_hist"]
    prev_macd_hist = previous["macd_hist"]

    fresh_reclaim = previous["close"] < previous["ema21"] and latest["close"] > latest["ema21"]
    above_ema21 = latest["close"] > latest["ema21"]
    above_ema50 = latest["close"] > latest["ema50"]
    above_ema200 = latest["close"] > latest["ema200"]
    macd_improving = macd_hist > prev_macd_hist

    # Base technical score
    if 3 <= price <= 50:
        score += 10
        dee_fit += 20
        reasons.append("Price fits Dee range")
    else:
        dee_fit -= 30
        reasons.append("Outside preferred price range")

    if above_ema21:
        score += 12
        dee_fit += 15
        reasons.append("Above EMA21")

    if above_ema50:
        score += 10
        dee_fit += 10
        reasons.append("Above EMA50")

    if above_ema200:
        score += 8
        dee_fit += 5
        reasons.append("Above EMA200")

    if fresh_reclaim:
        score += 20
        dee_fit += 25
        setup = "EMA21 Reclaim"
        reasons.append("Fresh EMA21 reclaim")

    # Entry location
    if 0 <= distance <= 2:
        score += 20
        dee_fit += 25
        reasons.append("Ideal EMA21 entry location")
    elif 2 < distance <= 4:
        score += 12
        dee_fit += 15
        reasons.append("Good EMA21 location")
    elif 4 < distance <= 6:
        score += 4
        dee_fit += 3
        reasons.append("Slightly extended")
    elif distance > 6:
        score -= 15
        dee_fit -= 25
        reasons.append("Too extended for Dee entry")
    elif distance < 0:
        score -= 10
        dee_fit -= 15
        reasons.append("Below EMA21")

    # Volume
    if rvol >= 2:
        score += 12
        dee_fit += 10
        reasons.append("Strong RVOL")
    elif rvol >= 1:
        score += 5
        dee_fit += 5
        reasons.append("Acceptable RVOL")
    elif rvol < 0.7:
        dee_fit -= 10
        reasons.append("Weak RVOL")

    # ATR
    if 4 <= atr_pct <= 12:
        score += 10
        dee_fit += 8
        reasons.append("Good swing range")
    elif atr_pct > 18:
        score -= 8
        dee_fit -= 12
        reasons.append("Volatility too wild")

    # RSI
    if 45 <= rsi <= 65:
        score += 10
        dee_fit += 12
        reasons.append("RSI healthy")
    elif rsi > 70:
        score -= 10
        dee_fit -= 15
        reasons.append("RSI too hot")

    # MACD
    if macd_improving and macd_hist > 0:
        score += 8
        dee_fit += 8
        reasons.append("MACD bullish")
    elif macd_improving:
        score += 4
        dee_fit += 5
        reasons.append("MACD improving early")

    if setup == "Watchlist" and above_ema21 and above_ema50 and 0 <= distance <= 4:
        setup = "Clean Pullback"

    score = max(0, min(score, 100))
    dee_fit = max(0, min(dee_fit, 100))
   
    if dee_fit >= 90:
        grade = "A+"
    elif dee_fit >= 80:
       grade = "A"
    elif dee_fit >= 70:
       grade = "B"
    elif dee_fit >= 60:
       grade = "C"
    else:
       grade = "Pass"
    
    return score, dee_fit, grade, setup, ", ".join(reasons)

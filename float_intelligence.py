from __future__ import annotations

from typing import Any

import requests


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def _fmp_float(symbol: str, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return {}
    response = requests.get(
        "https://financialmodelingprep.com/stable/shares-float",
        params={"symbol": symbol.upper(), "apikey": api_key},
        timeout=25,
    )
    if response.status_code != 200:
        return {}
    data = response.json()
    if isinstance(data, list) and data:
        return data[0]
    return data if isinstance(data, dict) else {}


def _alpha_overview(symbol: str, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return {}
    response = requests.get(
        "https://www.alphavantage.co/query",
        params={"function": "OVERVIEW", "symbol": symbol.upper(), "apikey": api_key},
        timeout=25,
    )
    if response.status_code != 200:
        return {}
    data = response.json()
    return data if isinstance(data, dict) and data.get("Symbol") else {}


def get_float_intelligence(symbol: str, fmp_api_key: str | None, alpha_vantage_api_key: str | None) -> dict[str, Any]:
    fmp = _fmp_float(symbol, fmp_api_key)
    alpha = _alpha_overview(symbol, alpha_vantage_api_key)

    float_shares = _number(fmp.get("floatShares") or fmp.get("float_shares") or alpha.get("SharesFloat"))
    outstanding = _number(fmp.get("outstandingShares") or fmp.get("outstanding_shares") or alpha.get("SharesOutstanding"))
    free_float_pct = _number(fmp.get("freeFloat") or fmp.get("free_float"))
    short_shares = _number(alpha.get("SharesShort"))
    short_prior = _number(alpha.get("SharesShortPriorMonth"))
    days_to_cover = _number(alpha.get("ShortRatio"))
    short_pct_float = (short_shares / float_shares * 100) if short_shares is not None and float_shares else None

    if float_shares is None and outstanding is None:
        return {"status": "Unavailable", "summary": "Float and share data was not returned by the connected providers."}

    if float_shares is not None:
        if float_shares <= 10_000_000:
            float_category = "Very Low Float"
            liquidity_risk = "High"
        elif float_shares <= 50_000_000:
            float_category = "Low Float"
            liquidity_risk = "Elevated"
        elif float_shares <= 200_000_000:
            float_category = "Medium Float"
            liquidity_risk = "Moderate"
        else:
            float_category = "Large Float"
            liquidity_risk = "Lower"
    else:
        float_category = "Unavailable"
        liquidity_risk = "Unavailable"

    squeeze_score = 0
    if short_pct_float is not None:
        squeeze_score += min(short_pct_float * 2.5, 70)
    if days_to_cover is not None:
        squeeze_score += min(days_to_cover * 5, 30)
    squeeze_score = round(max(0, min(100, squeeze_score)))

    short_trend = None
    if short_shares is not None and short_prior:
        short_trend = round((short_shares / short_prior - 1) * 100, 2)

    return {
        "status": "Available",
        "float_shares": round(float_shares) if float_shares is not None else None,
        "shares_outstanding": round(outstanding) if outstanding is not None else None,
        "free_float_pct": round(free_float_pct, 2) if free_float_pct is not None else None,
        "float_category": float_category,
        "liquidity_risk": liquidity_risk,
        "shares_short": round(short_shares) if short_shares is not None else None,
        "short_interest_pct_float": round(short_pct_float, 2) if short_pct_float is not None else None,
        "days_to_cover": round(days_to_cover, 2) if days_to_cover is not None else None,
        "short_interest_change_pct": short_trend,
        "squeeze_score": squeeze_score,
        "summary": f"{float_category} with {liquidity_risk.lower()} liquidity/volatility risk.",
        "disclaimer": "Short-interest fields may be delayed and should be confirmed with a dedicated short-interest source before trading.",
    }

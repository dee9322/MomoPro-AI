from __future__ import annotations

from typing import Any

import requests


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def _safe_json(url: str, params: dict[str, Any]) -> Any:
    try:
        response = requests.get(url, params=params, timeout=25)
        if response.status_code != 200:
            return None
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def _fmp_float(symbol: str, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return {}
    data = _safe_json(
        "https://financialmodelingprep.com/stable/shares-float",
        {"symbol": symbol.upper(), "apikey": api_key},
    )
    if isinstance(data, list) and data:
        return data[0]
    return data if isinstance(data, dict) else {}


def _alpha_overview(symbol: str, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return {}
    data = _safe_json(
        "https://www.alphavantage.co/query",
        {"function": "OVERVIEW", "symbol": symbol.upper(), "apikey": api_key},
    )
    return data if isinstance(data, dict) and data.get("Symbol") else {}


def _short_risk(short_pct: float | None, days_to_cover: float | None) -> str | None:
    if short_pct is None and days_to_cover is None:
        return None
    if (short_pct or 0) >= 20 or (days_to_cover or 0) >= 7:
        return "High"
    if (short_pct or 0) >= 10 or (days_to_cover or 0) >= 4:
        return "Elevated"
    return "Moderate / Low"


def get_float_intelligence(
    symbol: str,
    fmp_api_key: str | None,
    alpha_vantage_api_key: str | None,
) -> dict[str, Any]:
    fmp = _fmp_float(symbol, fmp_api_key)
    alpha = _alpha_overview(symbol, alpha_vantage_api_key)

    float_shares = _number(fmp.get("floatShares") or fmp.get("float_shares") or alpha.get("SharesFloat"))
    outstanding = _number(fmp.get("outstandingShares") or fmp.get("outstanding_shares") or alpha.get("SharesOutstanding"))
    free_float_pct = _number(fmp.get("freeFloat") or fmp.get("free_float"))
    short_shares = _number(alpha.get("SharesShort"))
    short_prior = _number(alpha.get("SharesShortPriorMonth"))
    days_to_cover = _number(alpha.get("ShortRatio"))
    short_pct_float = (
        short_shares / float_shares * 100
        if short_shares is not None and float_shares not in (None, 0)
        else None
    )

    if float_shares is None and outstanding is None and short_shares is None:
        return {
            "status": "Unavailable",
            "summary": "Float, shares, and short-interest data were not returned by the connected plans.",
            "score": None,
        }

    if float_shares is not None:
        if float_shares <= 10_000_000:
            float_category, liquidity_risk = "Very Low Float", "High"
        elif float_shares <= 50_000_000:
            float_category, liquidity_risk = "Low Float", "Elevated"
        elif float_shares <= 200_000_000:
            float_category, liquidity_risk = "Medium Float", "Moderate"
        else:
            float_category, liquidity_risk = "Large Float", "Lower"
    else:
        float_category, liquidity_risk = "Unavailable", "Unavailable"

    short_trend = None
    if short_shares is not None and short_prior not in (None, 0):
        short_trend = round((short_shares / short_prior - 1) * 100, 2)

    short_risk = _short_risk(short_pct_float, days_to_cover)
    squeeze_score = None
    if short_pct_float is not None and days_to_cover is not None:
        squeeze_score = round(
            max(0, min(100, min(short_pct_float * 2.5, 70) + min(days_to_cover * 5, 30)))
        )

    sources = []
    if fmp:
        sources.append("FMP Shares Float")
    if alpha:
        sources.append("Alpha Vantage Overview")

    return {
        "status": "Available",
        "score": None,
        "float_shares": round(float_shares) if float_shares is not None else None,
        "shares_outstanding": round(outstanding) if outstanding is not None else None,
        "free_float_pct": round(free_float_pct, 2) if free_float_pct is not None else None,
        "float_category": float_category,
        "liquidity_risk": liquidity_risk,
        "shares_short": round(short_shares) if short_shares is not None else None,
        "short_interest_pct_float": round(short_pct_float, 2) if short_pct_float is not None else None,
        "days_to_cover": round(days_to_cover, 2) if days_to_cover is not None else None,
        "short_interest_change_pct": short_trend,
        "short_risk": short_risk,
        "squeeze_score": squeeze_score,
        "source": " + ".join(sources) if sources else None,
        "data_quality": "Delayed / Reported",
        "summary": f"{float_category} with {liquidity_risk.lower()} liquidity/volatility risk.",
        "disclaimer": (
            "Short-interest values are delayed and may be unavailable on free plans. "
            "Squeeze score is shown only when both short percent of float and days to cover are available."
        ),
    }

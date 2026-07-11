from __future__ import annotations

from datetime import datetime
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


def _alpha_overview(symbol: str, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return {}
    data = _safe_json(
        "https://www.alphavantage.co/query",
        {"function": "OVERVIEW", "symbol": symbol.upper(), "apikey": api_key},
    )
    return data if isinstance(data, dict) and data.get("Symbol") else {}


def _fmp_position_summary(symbol: str, api_key: str | None) -> list[dict[str, Any]]:
    if not api_key:
        return []
    now = datetime.utcnow()
    current_quarter = (now.month - 1) // 3 + 1
    quarter = current_quarter - 1
    year = now.year
    if quarter == 0:
        quarter = 4
        year -= 1
    data = _safe_json(
        "https://financialmodelingprep.com/stable/institutional-ownership/symbol-positions-summary",
        {
            "symbol": symbol.upper(),
            "year": year,
            "quarter": quarter,
            "apikey": api_key,
        },
    )
    return data if isinstance(data, list) else []


def get_ownership_intelligence(
    symbol: str,
    fmp_api_key: str | None,
    alpha_vantage_api_key: str | None,
) -> dict[str, Any]:
    overview = _alpha_overview(symbol, alpha_vantage_api_key)
    positions = _fmp_position_summary(symbol, fmp_api_key)

    institutional_pct = _number(overview.get("PercentInstitutions"))
    insider_pct = _number(overview.get("PercentInsiders"))
    summary_row = positions[0] if positions else {}

    investors = _number(summary_row.get("investorsHolding") or summary_row.get("numberOfInvestors"))
    shares = _number(summary_row.get("numberOfInstitutionalShares") or summary_row.get("shares"))
    change = _number(summary_row.get("changeInShares") or summary_row.get("sharesChange"))

    sources = []
    if overview:
        sources.append("Alpha Vantage Overview")
    if positions:
        sources.append("FMP 13F Summary")

    if institutional_pct is None and insider_pct is None and not positions:
        return {
            "status": "Unavailable",
            "score": None,
            "summary": "Institutional ownership data was not returned by the connected plans.",
            "source": None,
        }

    score = 50.0
    if institutional_pct is not None:
        score += max(-20, min((institutional_pct - 40) * 0.5, 25))
    if change is not None and shares:
        prior_shares = max(abs(shares - change), 1)
        score += max(-20, min((change / prior_shares) * 100, 20))
    score = round(max(0, min(100, score)))

    if change is not None and change > 0:
        trend = "Increasing"
    elif change is not None and change < 0:
        trend = "Decreasing"
    elif change == 0:
        trend = "Stable"
    else:
        trend = "Unavailable"

    return {
        "status": "Available",
        "score": score,
        "institutional_ownership_pct": round(institutional_pct, 2) if institutional_pct is not None else None,
        "insider_ownership_pct": round(insider_pct, 2) if insider_pct is not None else None,
        "institution_count": round(investors) if investors is not None else None,
        "institutional_shares": round(shares) if shares is not None else None,
        "change_in_shares": round(change) if change is not None else None,
        "trend": trend,
        "source": " + ".join(sources) if sources else None,
        "data_quality": "Delayed / Reported",
        "summary": f"Reported institutional ownership trend is {trend.lower()}.",
        "disclaimer": "13F ownership is delayed and does not show real-time institutional positioning.",
    }

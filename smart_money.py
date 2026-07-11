from __future__ import annotations

from typing import Any

from float_intelligence import get_float_intelligence
from insider_intelligence import get_insider_activity
from institutional_intelligence import get_institutional_activity
from options_intelligence import get_options_activity
from ownership_intelligence import get_ownership_intelligence


def _score(section: dict[str, Any]) -> float | None:
    value = section.get("score")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def get_smart_money_intelligence(
    symbol: str,
    alpaca_api_key: str,
    alpaca_secret_key: str,
    alpha_vantage_api_key: str | None = None,
    finnhub_api_key: str | None = None,
    fmp_api_key: str | None = None,
) -> dict[str, Any]:
    institutional = get_institutional_activity(alpaca_api_key, alpaca_secret_key, symbol)
    options = get_options_activity(symbol, alpha_vantage_api_key)
    insiders = get_insider_activity(symbol, fmp_api_key, alpha_vantage_api_key)
    ownership = get_ownership_intelligence(symbol, fmp_api_key, alpha_vantage_api_key)
    float_data = get_float_intelligence(symbol, fmp_api_key, alpha_vantage_api_key)

    weighted_sections = [
        (institutional, 0.35),
        (options, 0.20),
        (insiders, 0.20),
        (ownership, 0.25),
    ]
    available = [(_score(section), weight) for section, weight in weighted_sections if _score(section) is not None]
    if available:
        total_weight = sum(weight for _, weight in available)
        overall = round(sum(score * weight for score, weight in available) / total_weight)
    else:
        overall = None

    if overall is None:
        verdict = "Unavailable"
    elif overall >= 75:
        verdict = "Strong Accumulation Evidence"
    elif overall >= 60:
        verdict = "Constructive Smart Money"
    elif overall >= 42:
        verdict = "Mixed / Neutral"
    elif overall >= 25:
        verdict = "Cautious / Distribution Risk"
    else:
        verdict = "Bearish Smart Money"

    available_count = sum(section.get("status") == "Available" for section, _ in weighted_sections)
    return {
        "symbol": symbol.upper(),
        "status": "Available" if available_count else "Unavailable",
        "overall_score": overall,
        "verdict": verdict,
        "available_modules": available_count,
        "institutional_activity": institutional,
        "options_activity": options,
        "insider_activity": insiders,
        "ownership": ownership,
        "float": float_data,
        "summary": (
            f"{verdict}. {available_count} of 4 scored Smart Money modules returned usable data."
            if available_count
            else "Smart Money data was unavailable from the connected providers."
        ),
        "data_note": "The score blends inferred OHLCV behavior with delayed reported data. It is not a real-time record of institutional orders.",
    }

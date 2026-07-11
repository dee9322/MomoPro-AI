from __future__ import annotations

from typing import Any

from float_intelligence import get_float_intelligence
from insider_intelligence import get_insider_activity
from institutional_intelligence import get_institutional_activity
from options_intelligence import get_options_activity
from ownership_intelligence import get_ownership_intelligence


SCORED_MODULES = ("institutional_activity", "options_activity", "insider_activity", "ownership")


def _score(section: dict[str, Any]) -> float | None:
    value = section.get("score")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _module_status(section: dict[str, Any]) -> str:
    return "Available" if section.get("status") == "Available" and _score(section) is not None else "Unavailable"


def get_smart_money_intelligence(
    symbol: str,
    alpaca_api_key: str,
    alpaca_secret_key: str,
    alpha_vantage_api_key: str | None = None,
    finnhub_api_key: str | None = None,
    fmp_api_key: str | None = None,
) -> dict[str, Any]:
    institutional = get_institutional_activity(alpaca_api_key, alpaca_secret_key, symbol)
    options = get_options_activity(symbol, finnhub_api_key, fmp_api_key)
    insiders = get_insider_activity(symbol, finnhub_api_key, fmp_api_key)
    ownership = get_ownership_intelligence(symbol, fmp_api_key, alpha_vantage_api_key)
    float_data = get_float_intelligence(symbol, fmp_api_key, alpha_vantage_api_key)

    sections = {
        "institutional_activity": institutional,
        "options_activity": options,
        "insider_activity": insiders,
        "ownership": ownership,
    }
    weights = {
        "institutional_activity": 0.35,
        "options_activity": 0.20,
        "insider_activity": 0.20,
        "ownership": 0.25,
    }

    available = [
        (_score(section), weights[name])
        for name, section in sections.items()
        if _score(section) is not None and section.get("status") == "Available"
    ]
    available_count = len(available)
    coverage_pct = round((available_count / len(SCORED_MODULES)) * 100)

    if available:
        total_weight = sum(weight for _, weight in available)
        overall = round(sum(score * weight for score, weight in available) / total_weight)
    else:
        overall = None

    preliminary = coverage_pct < 50
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

    if overall is None:
        assessment_label = "No Smart Money Read"
    elif preliminary:
        assessment_label = "Preliminary Smart Money Read"
    else:
        assessment_label = "Smart Money Read"

    module_status = {
        "Accumulation": _module_status(institutional),
        "Options": _module_status(options),
        "Insiders": _module_status(insiders),
        "Ownership": _module_status(ownership),
        "Float": "Available" if float_data.get("status") == "Available" else "Unavailable",
    }

    if overall is None:
        summary = "Smart Money data was unavailable from the connected providers."
    elif preliminary:
        summary = (
            f"Preliminary {verdict.lower()} based on {available_count} of 4 scored modules. "
            "Coverage is limited, so treat this as an incomplete assessment."
        )
    else:
        summary = f"{verdict}. {available_count} of 4 scored Smart Money modules returned usable data."

    return {
        "symbol": symbol.upper(),
        "status": "Available" if available_count else "Unavailable",
        "overall_score": overall,
        "verdict": verdict,
        "assessment_label": assessment_label,
        "preliminary": preliminary,
        "available_modules": available_count,
        "total_modules": len(SCORED_MODULES),
        "coverage_pct": coverage_pct,
        "module_status": module_status,
        "institutional_activity": institutional,
        "options_activity": options,
        "insider_activity": insiders,
        "ownership": ownership,
        "float": float_data,
        "summary": summary,
        "data_note": (
            "The score blends inferred OHLCV behavior with delayed reported data. "
            "It is not a real-time record of institutional orders."
        ),
    }

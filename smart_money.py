from __future__ import annotations

from typing import Any

from float_intelligence import get_float_intelligence
from insider_intelligence import get_insider_activity
from institutional_intelligence import get_institutional_activity
from options_intelligence import get_options_activity
from ownership_intelligence import get_ownership_intelligence


SCORED_WEIGHTS = {
    "institutional_activity": 0.35,
    "options_activity": 0.20,
    "insider_activity": 0.20,
    "ownership": 0.25,
}


def _score(section: dict[str, Any]) -> float | None:
    try:
        value = section.get("score")
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _usable(section: dict[str, Any]) -> bool:
    return section.get("status") == "Available"


def get_smart_money_intelligence(
    symbol: str,
    alpaca_api_key: str,
    alpaca_secret_key: str,
    alpha_vantage_api_key: str | None = None,
    finnhub_api_key: str | None = None,
    fmp_api_key: str | None = None,
) -> dict[str, Any]:
    institutional = get_institutional_activity(
        alpaca_api_key,
        alpaca_secret_key,
        symbol,
    )
    options = get_options_activity(
        symbol,
        alpaca_api_key,
        alpaca_secret_key,
    )
    # Correct provider order: Finnhub primary, FMP fallback.
    insiders = get_insider_activity(
        symbol,
        finnhub_api_key,
        fmp_api_key,
    )
    ownership = get_ownership_intelligence(
        symbol,
        fmp_api_key,
        alpha_vantage_api_key,
    )
    float_data = get_float_intelligence(
        symbol,
        fmp_api_key,
        alpha_vantage_api_key,
    )

    sections = {
        "institutional_activity": institutional,
        "options_activity": options,
        "insider_activity": insiders,
        "ownership": ownership,
        "float": float_data,
    }

    available_scored: list[tuple[float, float]] = []
    for name, weight in SCORED_WEIGHTS.items():
        section = sections[name]
        score = _score(section)
        if _usable(section) and score is not None:
            available_scored.append((score, weight))

    if available_scored:
        total_weight = sum(weight for _, weight in available_scored)
        overall = round(
            sum(score * weight for score, weight in available_scored)
            / total_weight
        )
    else:
        overall = None

    data_modules_available = sum(_usable(section) for section in sections.values())
    scored_modules_available = len(available_scored)
    coverage_pct = round(data_modules_available / len(sections) * 100)
    full_read = coverage_pct >= 60 and scored_modules_available >= 3

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

    read_status = "Full" if full_read else "Preliminary"
    if overall is None:
        read_status = "Unavailable"

    module_status = {
        name: {
            "available": _usable(section),
            "source": section.get("source") or section.get("data_source"),
            "quality": section.get("data_quality"),
        }
        for name, section in sections.items()
    }

    if overall is None:
        summary = "Smart Money data was unavailable from the connected providers."
    elif full_read:
        summary = (
            f"{verdict}. {data_modules_available} of 5 data modules and "
            f"{scored_modules_available} of 4 scored modules returned usable data."
        )
    else:
        summary = (
            f"Preliminary {verdict.lower()} read. Coverage is {coverage_pct}% "
            f"({data_modules_available} of 5 data modules), so treat the result as incomplete."
        )

    return {
        "symbol": symbol.upper(),
        "status": "Available" if data_modules_available else "Unavailable",
        "overall_score": overall,
        "verdict": verdict,
        "read_status": read_status,
        "coverage_pct": coverage_pct,
        "available_modules": data_modules_available,
        "total_modules": 5,
        "scored_modules_available": scored_modules_available,
        "total_scored_modules": 4,
        "confidence_eligible": full_read,
        "module_status": module_status,
        "institutional_activity": institutional,
        "options_activity": options,
        "insider_activity": insiders,
        "ownership": ownership,
        "float": float_data,
        "summary": summary,
        "data_note": (
            "The score blends inferred OHLCV behavior with delayed reported data. "
            "It is not a real-time record of institutional orders. Missing modules "
            "are excluded rather than treated as zero."
        ),
    }

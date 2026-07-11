import math
import re
from typing import Any


MODULE_WEIGHTS = {
    "trend": 0.20,
    "location": 0.20,
    "momentum": 0.15,
    "volume": 0.10,
    "opportunity": 0.15,
    "risk": 0.10,
    "structure": 0.10,
}

INTEGRATED_WEIGHTS = {
    "technical": 0.62,
    "market": 0.10,
    "sector": 0.07,
    "relative_strength": 0.08,
    "smart_money": 0.13,
}


def _valid_number(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _normalize_module(score):
    """Convert a MomoEngine module score from 0-25 into 0-100."""
    if not _valid_number(score):
        return 0

    return round(max(0.0, min(float(score), 25.0)) * 4)


def _quality_score(value):
    """Extract the numeric score from text such as 'Strong (68/100)'."""
    if not value:
        return None

    match = re.search(r"\((\d+(?:\.\d+)?)/100\)", str(value))

    if not match:
        return None

    return float(match.group(1))


def _risk_reward_score(risk_reward):
    if not _valid_number(risk_reward):
        return 35

    ratio = float(risk_reward)

    if ratio >= 3.0:
        return 100
    if ratio >= 2.0:
        return 85
    if ratio >= 1.5:
        return 70
    if ratio >= 1.0:
        return 45

    return 20


def _structure_score(risk_reward_data, levels):
    ratio_score = _risk_reward_score(
        risk_reward_data.get("Risk Reward")
    )

    zone_scores = []

    for key in (
        "Support 1 Quality",
        "Resistance 1 Quality",
    ):
        score = _quality_score(levels.get(key))

        if score is not None:
            zone_scores.append(score)

    zone_score = (
        sum(zone_scores) / len(zone_scores)
        if zone_scores
        else 40
    )

    return round((ratio_score * 0.60) + (zone_score * 0.40))


def _rating(score: float | int) -> str:
    if score >= 90:
        return "Very High"
    if score >= 80:
        return "High"
    if score >= 70:
        return "Good"
    if score >= 60:
        return "Moderate"
    return "Low"


def calculate_confidence(modules, risk_reward_data, levels):
    """
    Calculate transparent technical Momo Engine Confidence.

    This score intentionally excludes market, sector, news, and AI inputs.
    Those are layered in separately by calculate_integrated_confidence().
    """
    breakdown = {
        "Trend": _normalize_module(modules.get("trend")),
        "Location": _normalize_module(modules.get("location")),
        "Momentum": _normalize_module(modules.get("momentum")),
        "Volume": _normalize_module(modules.get("volume")),
        "Opportunity": _normalize_module(modules.get("opportunity")),
        "Risk": _normalize_module(modules.get("risk")),
        "Structure": _structure_score(risk_reward_data, levels),
    }

    weighted_total = (
        breakdown["Trend"] * MODULE_WEIGHTS["trend"]
        + breakdown["Location"] * MODULE_WEIGHTS["location"]
        + breakdown["Momentum"] * MODULE_WEIGHTS["momentum"]
        + breakdown["Volume"] * MODULE_WEIGHTS["volume"]
        + breakdown["Opportunity"] * MODULE_WEIGHTS["opportunity"]
        + breakdown["Risk"] * MODULE_WEIGHTS["risk"]
        + breakdown["Structure"] * MODULE_WEIGHTS["structure"]
    )

    confidence = round(max(0, min(weighted_total, 100)))

    return {
        "Momo Confidence": confidence,
        "Confidence Rating": _rating(confidence),
        "Confidence Breakdown": breakdown,
    }


def _sector_score_from_context(
    market_context: dict[str, Any] | None,
    relative_strength: dict[str, Any] | None,
) -> float | None:
    market_context = market_context or {}
    relative_strength = relative_strength or {}

    sector_name = relative_strength.get("sector_name")
    sector_etf = relative_strength.get("sector_etf")
    rankings = market_context.get("sectors", {}).get("rankings", [])

    for item in rankings:
        if (
            sector_etf
            and item.get("symbol") == sector_etf
        ) or (
            sector_name
            and item.get("sector") == sector_name
        ):
            return float(item["score"]) if _valid_number(item.get("score")) else None

    leaders = market_context.get("sectors", {}).get("leaders", [])
    if leaders and _valid_number(leaders[0].get("score")):
        return float(leaders[0]["score"])

    return None


def calculate_integrated_confidence(
    technical_confidence: float | int | None,
    market_context: dict[str, Any] | None,
    relative_strength: dict[str, Any] | None,
    smart_money_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Blend the stock's technical confidence with live market context.

    The technical engine remains the largest component. Missing market inputs
    are reweighted out rather than treated as zero, so unavailable data does
    not unfairly punish a setup.
    """
    market_context = market_context or {}
    relative_strength = relative_strength or {}
    smart_money_context = smart_money_context or {}

    breakdown: dict[str, float | None] = {
        "Technical": (
            float(technical_confidence)
            if _valid_number(technical_confidence)
            else None
        ),
        "Market": (
            float(market_context.get("market_score"))
            if _valid_number(market_context.get("market_score"))
            else None
        ),
        "Sector": _sector_score_from_context(
            market_context,
            relative_strength,
        ),
        "Relative Strength": (
            float(relative_strength.get("score"))
            if _valid_number(relative_strength.get("score"))
            else None
        ),
        "Smart Money": (
            float(smart_money_context.get("overall_score"))
            if (
                _valid_number(smart_money_context.get("overall_score"))
                and _valid_number(smart_money_context.get("coverage_pct"))
                and float(smart_money_context.get("coverage_pct")) >= 50
            )
            else None
        ),
    }

    components = [
        (breakdown["Technical"], INTEGRATED_WEIGHTS["technical"]),
        (breakdown["Market"], INTEGRATED_WEIGHTS["market"]),
        (breakdown["Sector"], INTEGRATED_WEIGHTS["sector"]),
        (
            breakdown["Relative Strength"],
            INTEGRATED_WEIGHTS["relative_strength"],
        ),
        (
            breakdown["Smart Money"],
            INTEGRATED_WEIGHTS["smart_money"],
        ),
    ]

    available = [
        (value, weight)
        for value, weight in components
        if value is not None
    ]

    if not available:
        return {
            "Integrated Confidence": None,
            "Integrated Rating": "Unavailable",
            "Integrated Breakdown": breakdown,
            "Adjustment": None,
        }

    total_weight = sum(weight for _, weight in available)
    integrated = round(
        sum(value * weight for value, weight in available) / total_weight
    )
    integrated = max(0, min(integrated, 100))

    technical = breakdown["Technical"]
    adjustment = (
        round(integrated - technical)
        if technical is not None
        else None
    )

    return {
        "Integrated Confidence": integrated,
        "Integrated Rating": _rating(integrated),
        "Integrated Breakdown": breakdown,
        "Adjustment": adjustment,
    }

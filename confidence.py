import math
import re


MODULE_WEIGHTS = {
    "trend": 0.20,
    "location": 0.20,
    "momentum": 0.15,
    "volume": 0.10,
    "opportunity": 0.15,
    "risk": 0.10,
    "structure": 0.10,
}


def _valid_number(value):
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


def calculate_confidence(modules, risk_reward_data, levels):
    """
    Calculate transparent Momo Engine Confidence.

    The confidence percentage uses the active technical modules plus a
    structural score derived from risk/reward and the quality of the nearest
    support and resistance zones. Future market, sector, news, and AI inputs
    will remain separate and can be added without changing this interface.
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

    if confidence >= 90:
        rating = "Very High"
    elif confidence >= 80:
        rating = "High"
    elif confidence >= 70:
        rating = "Good"
    elif confidence >= 60:
        rating = "Moderate"
    else:
        rating = "Low"

    return {
        "Momo Confidence": confidence,
        "Confidence Rating": rating,
        "Confidence Breakdown": breakdown,
    }

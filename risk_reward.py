import math


def _valid_price(value):
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def calculate_risk_reward(close, levels):
    """
    Calculates structural reference risk/reward.

    Reference entry:
        Current closing price.

    Risk reference:
        Nearest valid support below the entry.

    Reward reference:
        Nearest valid resistance above the entry.

    Final entry, stop, and T1/T2/T3 logic will be built separately.
    """
    entry = float(close)

    support_values = [
        levels.get("Support 1"),
        levels.get("Support 2"),
        levels.get("Support 3"),
    ]

    resistance_values = [
        levels.get("Resistance 1"),
        levels.get("Resistance 2"),
        levels.get("Resistance 3"),
    ]

    valid_supports = sorted(
        {
            float(value)
            for value in support_values
            if _valid_price(value) and float(value) < entry
        },
        reverse=True,
    )

    valid_resistances = sorted(
        {
            float(value)
            for value in resistance_values
            if _valid_price(value) and float(value) > entry
        }
    )

    support = valid_supports[0] if valid_supports else None
    resistance = valid_resistances[0] if valid_resistances else None

    if support is None or resistance is None:
        return {
            "Reference Entry": round(entry, 2),
            "Risk Reference": (
                round(support, 2) if support is not None else None
            ),
            "Reward Reference": (
                round(resistance, 2) if resistance is not None else None
            ),
            "Risk Per Share": None,
            "Reward Per Share": None,
            "Risk Reward": None,
            "Risk Reward Status": "Insufficient structural levels",
        }

    risk_per_share = entry - support
    reward_per_share = resistance - entry

    if risk_per_share <= 0 or reward_per_share <= 0:
        return {
            "Reference Entry": round(entry, 2),
            "Risk Reference": round(support, 2),
            "Reward Reference": round(resistance, 2),
            "Risk Per Share": None,
            "Reward Per Share": None,
            "Risk Reward": None,
            "Risk Reward Status": "Invalid structural relationship",
        }

    risk_reward = reward_per_share / risk_per_share

    if risk_reward >= 3:
        status = "Excellent"
    elif risk_reward >= 2:
        status = "Favorable"
    elif risk_reward >= 1.5:
        status = "Acceptable"
    elif risk_reward >= 1:
        status = "Weak"
    else:
        status = "Unfavorable"

    return {
        "Reference Entry": round(entry, 2),
        "Risk Reference": round(support, 2),
        "Reward Reference": round(resistance, 2),
        "Risk Per Share": round(risk_per_share, 2),
        "Reward Per Share": round(reward_per_share, 2),
        "Risk Reward": round(risk_reward, 2),
        "Risk Reward Status": status,
    }

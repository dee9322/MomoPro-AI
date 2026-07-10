import math


def _valid_price(value):
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def calculate_targets(entry, risk_per_share, levels):
    """
    Calculates structural T1, T2, and T3 from resistance levels.

    T1:
        Nearest resistance above the reference entry.

    T2:
        Second resistance above the reference entry.

    T3:
        Third resistance above the reference entry.

    R multiples use the structural risk per share calculated
    by the Risk/Reward Engine.
    """
    entry = float(entry)

    resistance_values = [
        levels.get("Resistance 1"),
        levels.get("Resistance 2"),
        levels.get("Resistance 3"),
    ]

    targets = sorted(
        {
            float(value)
            for value in resistance_values
            if _valid_price(value) and float(value) > entry
        }
    )

    while len(targets) < 3:
        targets.append(None)

    valid_risk = (
        _valid_price(risk_per_share)
        and float(risk_per_share) > 0
    )

    result = {}

    for index, target in enumerate(targets[:3], start=1):
        target_name = f"T{index}"

        if target is None:
            result[target_name] = None
            result[f"{target_name} Upside %"] = None
            result[f"{target_name} R"] = None
            continue

        reward = target - entry
        upside_pct = (reward / entry) * 100

        reward_r = (
            reward / float(risk_per_share)
            if valid_risk
            else None
        )

        result[target_name] = round(target, 2)
        result[f"{target_name} Upside %"] = round(
            upside_pct,
            2,
        )
        result[f"{target_name} R"] = (
            round(reward_r, 2)
            if reward_r is not None
            else None
        )

    return result

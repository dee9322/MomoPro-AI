import math


def _valid_number(value):
    return value is not None and not math.isnan(value)


def calculate_levels(latest):
    close = float(latest["close"])

    support_candidates = [
        latest.get("ema21"),
        latest.get("ema50"),
        latest.get("ema200"),
        latest.get("prior_20_low"),
        latest.get("prior_60_low"),
    ]

    resistance_candidates = [
        latest.get("prior_20_high"),
        latest.get("prior_60_high"),
        latest.get("prior_120_high"),
    ]

    supports = sorted(
        {
            round(float(level), 2)
            for level in support_candidates
            if _valid_number(level) and float(level) < close
        },
        reverse=True,
    )

    resistances = sorted(
        {
            round(float(level), 2)
            for level in resistance_candidates
            if _valid_number(level) and float(level) > close
        }
    )

    while len(supports) < 3:
        supports.append(None)

    while len(resistances) < 3:
        resistances.append(None)

    return {
        "Support 1": supports[0],
        "Support 2": supports[1],
        "Support 3": supports[2],
        "Resistance 1": resistances[0],
        "Resistance 2": resistances[1],
        "Resistance 3": resistances[2],
    }

import math

import numpy as np
import pandas as pd


PIVOT_WINDOW = 3
ATR_ZONE_MULTIPLIER = 0.35
MIN_ZONE_PERCENT = 0.006
MAX_LOOKBACK_BARS = 180


def _valid_number(value):
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _find_pivots(df):
    data = df.copy()

    rolling_high = data["high"].rolling(
        window=(PIVOT_WINDOW * 2) + 1,
        center=True,
    ).max()

    rolling_low = data["low"].rolling(
        window=(PIVOT_WINDOW * 2) + 1,
        center=True,
    ).min()

    data["pivot_high"] = np.where(
        data["high"] >= rolling_high,
        data["high"],
        np.nan,
    )

    data["pivot_low"] = np.where(
        data["low"] <= rolling_low,
        data["low"],
        np.nan,
    )

    return data


def _cluster_prices(points, tolerance):
    if not points:
        return []

    sorted_points = sorted(points, key=lambda item: item["price"])
    clusters = []

    for point in sorted_points:
        matching_cluster = None

        for cluster in clusters:
            if abs(point["price"] - cluster["center"]) <= tolerance:
                matching_cluster = cluster
                break

        if matching_cluster is None:
            clusters.append(
                {
                    "center": point["price"],
                    "points": [point],
                }
            )
        else:
            matching_cluster["points"].append(point)

            prices = [
                item["price"]
                for item in matching_cluster["points"]
            ]

            matching_cluster["center"] = sum(prices) / len(prices)

    return clusters


def _score_zone(cluster, df, current_index, avg_volume):
    points = cluster["points"]
    center = float(cluster["center"])

    touches = len(points)
    rejection_score = 0.0
    volume_score = 0.0
    recency_score = 0.0

    for point in points:
        row_index = point["index"]

        if row_index < 0 or row_index >= len(df):
            continue

        row = df.iloc[row_index]

        candle_range = max(
            float(row["high"]) - float(row["low"]),
            0.000001,
        )

        body = abs(float(row["close"]) - float(row["open"]))
        upper_wick = float(row["high"]) - max(
            float(row["open"]),
            float(row["close"]),
        )
        lower_wick = min(
            float(row["open"]),
            float(row["close"]),
        ) - float(row["low"])

        if point["type"] == "resistance":
            rejection_strength = max(upper_wick, body) / candle_range
        else:
            rejection_strength = max(lower_wick, body) / candle_range

        rejection_score += min(rejection_strength, 1.5)

        if avg_volume > 0:
            relative_volume = float(row["volume"]) / avg_volume
            volume_score += min(relative_volume, 3.0)

        bars_ago = current_index - row_index

        if bars_ago <= 20:
            recency_score += 3
        elif bars_ago <= 60:
            recency_score += 2
        elif bars_ago <= 120:
            recency_score += 1

    touch_points = min(touches * 4, 24)
    rejection_points = min(rejection_score * 4, 28)
    volume_points = min(volume_score * 2, 24)
    recency_points = min(recency_score, 24)

    quality_score = round(
        min(
            touch_points
            + rejection_points
            + volume_points
            + recency_points,
            100,
        )
    )

    if quality_score >= 75:
        quality = "Major"
    elif quality_score >= 50:
        quality = "Strong"
    elif quality_score >= 30:
        quality = "Moderate"
    else:
        quality = "Minor"

    return {
        "price": round(center, 2),
        "touches": touches,
        "quality_score": quality_score,
        "quality": quality,
    }


def calculate_levels(df):
    """
    Detects structural support and resistance zones from historical OHLCV.

    The engine uses:
    - pivot highs and lows
    - clustered nearby reactions
    - touch count
    - wick/body rejection strength
    - relative reaction volume
    - recency

    OHLCV can suggest institutional-style accumulation/distribution,
    but it cannot identify the actual buyer or seller.
    """
    if df is None or df.empty:
        return _empty_levels()

    data = df.tail(MAX_LOOKBACK_BARS).copy().reset_index(drop=True)

    required_columns = {
        "open",
        "high",
        "low",
        "close",
        "volume",
        "atr14",
    }

    if not required_columns.issubset(data.columns):
        return _empty_levels()

    data = _find_pivots(data)

    latest = data.iloc[-1]
    close = float(latest["close"])
    atr = float(latest["atr14"])

    tolerance = max(
        atr * ATR_ZONE_MULTIPLIER,
        close * MIN_ZONE_PERCENT,
    )

    avg_volume = float(
        data["volume"].tail(20).mean()
    )

    pivot_points = []

    for index, row in data.iterrows():
        if _valid_number(row.get("pivot_high")):
            pivot_points.append(
                {
                    "price": float(row["pivot_high"]),
                    "index": index,
                    "type": "resistance",
                }
            )

        if _valid_number(row.get("pivot_low")):
            pivot_points.append(
                {
                    "price": float(row["pivot_low"]),
                    "index": index,
                    "type": "support",
                }
            )

    resistance_points = [
        point
        for point in pivot_points
        if point["type"] == "resistance"
    ]

    support_points = [
        point
        for point in pivot_points
        if point["type"] == "support"
    ]

    resistance_clusters = _cluster_prices(
        resistance_points,
        tolerance,
    )

    support_clusters = _cluster_prices(
        support_points,
        tolerance,
    )

    current_index = len(data) - 1

    resistance_zones = [
        _score_zone(
            cluster,
            data,
            current_index,
            avg_volume,
        )
        for cluster in resistance_clusters
        if float(cluster["center"]) > close
    ]

    support_zones = [
        _score_zone(
            cluster,
            data,
            current_index,
            avg_volume,
        )
        for cluster in support_clusters
        if float(cluster["center"]) < close
    ]

    resistance_zones = sorted(
        resistance_zones,
        key=lambda zone: (
            zone["price"],
            -zone["quality_score"],
        ),
    )

    support_zones = sorted(
        support_zones,
        key=lambda zone: (
            -zone["price"],
            -zone["quality_score"],
        ),
    )

    resistance_zones = _remove_overlapping_zones(
        resistance_zones,
        tolerance,
    )

    support_zones = _remove_overlapping_zones(
        support_zones,
        tolerance,
    )

    while len(resistance_zones) < 3:
        resistance_zones.append(None)

    while len(support_zones) < 3:
        support_zones.append(None)

    return {
        "Support 1": _zone_price(support_zones[0]),
        "Support 2": _zone_price(support_zones[1]),
        "Support 3": _zone_price(support_zones[2]),
        "Resistance 1": _zone_price(resistance_zones[0]),
        "Resistance 2": _zone_price(resistance_zones[1]),
        "Resistance 3": _zone_price(resistance_zones[2]),

        "Support 1 Quality": _zone_quality(support_zones[0]),
        "Support 2 Quality": _zone_quality(support_zones[1]),
        "Support 3 Quality": _zone_quality(support_zones[2]),

        "Resistance 1 Quality": _zone_quality(resistance_zones[0]),
        "Resistance 2 Quality": _zone_quality(resistance_zones[1]),
        "Resistance 3 Quality": _zone_quality(resistance_zones[2]),

        "Support 1 Touches": _zone_touches(support_zones[0]),
        "Support 2 Touches": _zone_touches(support_zones[1]),
        "Support 3 Touches": _zone_touches(support_zones[2]),

        "Resistance 1 Touches": _zone_touches(resistance_zones[0]),
        "Resistance 2 Touches": _zone_touches(resistance_zones[1]),
        "Resistance 3 Touches": _zone_touches(resistance_zones[2]),
    }


def _remove_overlapping_zones(zones, tolerance):
    filtered = []

    for zone in zones:
        overlapping_index = None

        for index, existing in enumerate(filtered):
            if abs(zone["price"] - existing["price"]) <= tolerance:
                overlapping_index = index
                break

        if overlapping_index is None:
            filtered.append(zone)
        elif (
            zone["quality_score"]
            > filtered[overlapping_index]["quality_score"]
        ):
            filtered[overlapping_index] = zone

    return filtered


def _zone_price(zone):
    if not zone:
        return None

    return zone["price"]


def _zone_quality(zone):
    if not zone:
        return None

    return (
        f'{zone["quality"]} '
        f'({zone["quality_score"]}/100)'
    )


def _zone_touches(zone):
    if not zone:
        return None

    return zone["touches"]


def _empty_levels():
    return {
        "Support 1": None,
        "Support 2": None,
        "Support 3": None,
        "Resistance 1": None,
        "Resistance 2": None,
        "Resistance 3": None,

        "Support 1 Quality": None,
        "Support 2 Quality": None,
        "Support 3 Quality": None,

        "Resistance 1 Quality": None,
        "Resistance 2 Quality": None,
        "Resistance 3 Quality": None,

        "Support 1 Touches": None,
        "Support 2 Touches": None,
        "Support 3 Touches": None,

        "Resistance 1 Touches": None,
        "Resistance 2 Touches": None,
        "Resistance 3 Touches": None,
    }

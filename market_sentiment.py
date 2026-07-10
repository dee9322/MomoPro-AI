from __future__ import annotations

import html
import re
from typing import Any

import requests


CBOE_DAILY_STATS_URL = (
    "https://www.cboe.com/markets/us/options/market-statistics/daily/"
)
REQUEST_TIMEOUT_SECONDS = 10


def _empty_sentiment(message: str) -> dict[str, Any]:
    return {
        "status": "Unavailable",
        "fear_greed_score": None,
        "fear_greed_label": "Unavailable",
        "risk_appetite": "Unavailable",
        "total_put_call_ratio": None,
        "equity_put_call_ratio": None,
        "put_call_signal": "Unavailable",
        "summary": message,
        "warning": None,
        "source": "Cboe Daily Market Statistics + Momo composite",
    }


def _extract_ratio(page_text: str, label: str) -> float | None:
    pattern = rf"{re.escape(label)}\s+([0-9]+(?:\.[0-9]+)?)"
    match = re.search(pattern, page_text, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _fetch_cboe_put_call() -> dict[str, float | None]:
    response = requests.get(
        CBOE_DAILY_STATS_URL,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; MomoProAI/1.0; "
                "+https://streamlit.io)"
            )
        },
    )
    response.raise_for_status()

    clean_text = re.sub(r"<[^>]+>", " ", response.text)
    clean_text = html.unescape(clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text)

    return {
        "total": _extract_ratio(clean_text, "TOTAL PUT/CALL RATIO"),
        "equity": _extract_ratio(clean_text, "EQUITY PUT/CALL RATIO"),
    }


def _put_call_score(ratio: float | None) -> float | None:
    if ratio is None:
        return None

    if ratio <= 0.60:
        return 92
    if ratio <= 0.75:
        return 80
    if ratio <= 0.90:
        return 66
    if ratio <= 1.05:
        return 50
    if ratio <= 1.20:
        return 35
    if ratio <= 1.40:
        return 20
    return 8


def _put_call_signal(ratio: float | None) -> str:
    if ratio is None:
        return "Unavailable"
    if ratio <= 0.60:
        return "Very Bullish / Complacent"
    if ratio <= 0.80:
        return "Bullish"
    if ratio <= 1.05:
        return "Neutral"
    if ratio <= 1.25:
        return "Defensive"
    return "Fearful"


def _fear_greed_label(score: int) -> str:
    if score >= 75:
        return "Extreme Greed"
    if score >= 56:
        return "Greed"
    if score >= 45:
        return "Neutral"
    if score >= 25:
        return "Fear"
    return "Extreme Fear"


def _risk_appetite(label: str) -> str:
    if label in {"Extreme Greed", "Greed"}:
        return "Risk Seeking"
    if label == "Neutral":
        return "Balanced"
    return "Defensive"


def _build_summary(
    label: str,
    total_put_call: float | None,
    market_score: float | None,
    breadth_score: float | None,
) -> str:
    parts = [f"Momo sentiment is {label.lower()}."]

    if total_put_call is not None:
        parts.append(
            f"The Cboe total put/call ratio is {total_put_call:.2f}, "
            f"which reads as {_put_call_signal(total_put_call).lower()}."
        )

    if market_score is not None and breadth_score is not None:
        if market_score >= 65 and breadth_score >= 60:
            parts.append(
                "Price trend and participation are broadly supportive of risk appetite."
            )
        elif market_score <= 40 or breadth_score <= 40:
            parts.append(
                "Weak trend or participation argues for more defensive trade selection."
            )
        else:
            parts.append(
                "Trend and participation are mixed, so selectivity remains important."
            )

    return " ".join(parts)


def get_market_sentiment(
    market_score: float | int | None,
    breadth: dict[str, Any] | None,
    indexes: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    Build a transparent Momo Fear & Greed composite.

    Inputs:
    - broad-market trend score
    - market breadth score
    - inverse VIXY trend score as a volatility-risk proxy
    - official Cboe daily put/call ratio when available

    This is intentionally labeled as Momo Fear & Greed rather than the
    proprietary CNN Fear & Greed Index.
    """
    breadth = breadth or {}
    indexes = indexes or {}

    try:
        put_call = _fetch_cboe_put_call()
    except Exception:
        put_call = {"total": None, "equity": None}

    breadth_score = breadth.get("breadth_score")
    vixy_score = indexes.get("VIXY", {}).get("score")
    volatility_score = (
        max(0, min(100 - float(vixy_score), 100))
        if vixy_score is not None
        else None
    )
    options_score = _put_call_score(put_call.get("total"))

    components = [
        (market_score, 0.35),
        (breadth_score, 0.30),
        (volatility_score, 0.20),
        (options_score, 0.15),
    ]

    available = [
        (float(value), weight)
        for value, weight in components
        if value is not None
    ]

    if not available:
        return _empty_sentiment("Market sentiment could not be calculated.")

    total_weight = sum(weight for _, weight in available)
    composite = sum(value * weight for value, weight in available) / total_weight
    score = round(max(0, min(composite, 100)))

    label = _fear_greed_label(score)
    warning = None

    if label == "Extreme Greed":
        warning = (
            "Sentiment is very optimistic. Favor disciplined entries and avoid "
            "chasing extended moves."
        )
    elif label == "Extreme Fear":
        warning = (
            "Sentiment is deeply defensive. Reversal opportunities may develop, "
            "but confirmation and smaller risk are appropriate."
        )

    return {
        "status": "Available",
        "fear_greed_score": score,
        "fear_greed_label": label,
        "risk_appetite": _risk_appetite(label),
        "total_put_call_ratio": put_call.get("total"),
        "equity_put_call_ratio": put_call.get("equity"),
        "put_call_signal": _put_call_signal(put_call.get("total")),
        "summary": _build_summary(
            label,
            put_call.get("total"),
            float(market_score) if market_score is not None else None,
            float(breadth_score) if breadth_score is not None else None,
        ),
        "warning": warning,
        "source": "Cboe Daily Market Statistics + Momo composite",
    }

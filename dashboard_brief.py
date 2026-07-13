from __future__ import annotations

from typing import Any


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_today_trading_plan(
    market_context: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    alert_count: int,
    open_trade_count: int,
    headline_count: int,
) -> dict[str, str]:
    if not market_context:
        return {
            "headline": "Load Market Context before setting today’s risk posture.",
            "plan": (
                "The command center has not been refreshed yet. Load Market Context, run the Scanner, "
                "and review the highest-ranked candidates before considering a new position."
            ),
            "risk_posture": "Unrated",
        }

    market_trend = market_context.get("market_trend", "Unavailable")
    risk = market_context.get("risk_environment", "Unavailable")
    score = _number(market_context.get("market_score"))
    breadth = market_context.get("breadth", {})
    breadth_status = breadth.get("breadth_status", "Unavailable")
    sentiment = market_context.get("sentiment", {})
    sentiment_label = sentiment.get("fear_greed_label", "Unavailable")
    sectors = market_context.get("sectors", {})
    leaders = sectors.get("leaders") or []
    leader_names = [item.get("sector") for item in leaders[:2] if item.get("sector")]

    if score is not None and score >= 75:
        posture = "Normal risk, but require clean entries"
        action = "Conditions support selective momentum exposure."
    elif score is not None and score >= 58:
        posture = "Moderate risk"
        action = "Favor the cleanest setups and avoid chasing extended names."
    elif score is not None and score >= 42:
        posture = "Reduced risk"
        action = "Trade smaller, demand confirmation, and prioritize nearby invalidation levels."
    else:
        posture = "Defensive"
        action = "Protect capital, avoid marginal setups, and wait for market confirmation."

    top = candidates[0] if candidates else None
    top_text = (
        f"The highest-ranked scanner candidate is {top.get('Symbol')} "
        f"({top.get('Grade', '—')}, Momo Score {top.get('Momo Score', '—')})."
        if top
        else "No scanner candidates are loaded yet."
    )
    leader_text = (
        f"Leadership is concentrated in {', '.join(leader_names)}."
        if leader_names
        else "Sector leadership is not yet available."
    )

    headline = f"{market_trend} market · {risk} · {breadth_status} breadth"
    plan = (
        f"{action} {leader_text} Sentiment is {str(sentiment_label).lower()}. "
        f"{top_text} You have {alert_count} unread watchlist alert{'s' if alert_count != 1 else ''}, "
        f"{open_trade_count} open trade{'s' if open_trade_count != 1 else ''}, and "
        f"{headline_count} ranked market headline{'s' if headline_count != 1 else ''}. "
        "Confirm price location, risk/reward, and catalyst timing before entry."
    )
    return {"headline": headline, "plan": plan, "risk_posture": posture}

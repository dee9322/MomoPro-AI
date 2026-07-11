import json
import math
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field


MODEL = "gpt-5.4-mini"


class AIStockDecision(BaseModel):
    decision: str = Field(
        description="One of: Entry Ready, Bullish Watch, Wait for Confirmation, Neutral, Avoid"
    )
    confidence: int = Field(ge=0, le=100)
    summary: str
    strengths: list[str]
    concerns: list[str]
    what_improves_setup: list[str]
    invalidation: list[str]


def _valid_number(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _number(value: Any) -> float | None:
    return float(value) if _valid_number(value) else None


def _quality_number(value: Any) -> int | None:
    if not value:
        return None

    text = str(value)
    marker = "/100"

    if marker not in text:
        return None

    left = text.split(marker, 1)[0]
    digits = ""

    for character in reversed(left):
        if character.isdigit():
            digits = character + digits
        elif digits:
            break

    return int(digits) if digits else None


def build_momo_engine_decision(
    stock: Any,
    market_context: dict[str, Any] | None = None,
    relative_strength: dict[str, Any] | None = None,
    news_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a transparent rule-based decision from stock and market data."""

    market_context = market_context or {}
    relative_strength = relative_strength or {}
    news_context = news_context or {}

    confidence = _number(stock.get("Momo Confidence")) or 0
    dee_fit = _number(stock.get("Dee Fit")) or 0
    score = _number(stock.get("Score")) or 0
    risk_reward = _number(stock.get("Risk Reward"))
    distance = _number(stock.get("Distance EMA21 %"))
    rvol = _number(stock.get("RVOL"))
    t1_r = _number(stock.get("T1 R"))
    support_quality = _quality_number(stock.get("Support 1 Quality"))
    resistance_quality = _quality_number(stock.get("Resistance 1 Quality"))

    strengths: list[str] = []
    concerns: list[str] = []

    if confidence >= 80:
        strengths.append(f"High rule-based confidence at {confidence:.0f}%")
    elif confidence >= 70:
        strengths.append(f"Constructive rule-based confidence at {confidence:.0f}%")
    else:
        concerns.append(f"Momo confidence is only {confidence:.0f}%")

    if dee_fit >= 80:
        strengths.append(f"Strong Dee Fit at {dee_fit:.0f}")
    elif dee_fit < 70:
        concerns.append(f"Dee Fit is below the preferred range at {dee_fit:.0f}")

    if distance is not None:
        if 0 <= distance <= 4:
            strengths.append(f"Price is in a workable EMA21 area ({distance:.2f}% above)")
        elif distance > 6:
            concerns.append(f"Price is extended {distance:.2f}% above EMA21")
        elif distance < 0:
            concerns.append(f"Price is {abs(distance):.2f}% below EMA21")

    if rvol is not None:
        if rvol >= 1.5:
            strengths.append(f"Strong participation with {rvol:.2f} RVOL")
        elif rvol < 0.7:
            concerns.append(f"Weak participation with only {rvol:.2f} RVOL")

    if risk_reward is not None:
        if risk_reward >= 2:
            strengths.append(f"Favorable structural risk/reward at {risk_reward:.2f}R")
        elif risk_reward < 1.5:
            concerns.append(f"Structural risk/reward is limited at {risk_reward:.2f}R")
    else:
        concerns.append("A complete structural risk/reward could not be calculated")

    if t1_r is not None and t1_r < 1:
        concerns.append(f"T1 offers only {t1_r:.2f}R from the reference entry")

    if support_quality is not None:
        if support_quality >= 60:
            strengths.append(f"Nearest support is well confirmed ({support_quality}/100)")
        elif support_quality < 35:
            concerns.append(f"Nearest support is lightly confirmed ({support_quality}/100)")

    if resistance_quality is not None and resistance_quality >= 60:
        strengths.append(f"Nearest resistance is clearly established ({resistance_quality}/100)")

    market_score = _number(market_context.get("market_score"))
    breadth = market_context.get("breadth", {})
    sentiment = market_context.get("sentiment", {})
    sectors = market_context.get("sectors", {})
    rs_score = _number(relative_strength.get("score"))

    if market_score is not None:
        if market_score >= 70:
            strengths.append(f"Broad market backdrop is supportive ({market_score:.0f}/100)")
        elif market_score < 45:
            concerns.append(f"Broad market backdrop is weak ({market_score:.0f}/100)")

    breadth_score = _number(breadth.get("breadth_score"))
    if breadth_score is not None:
        if breadth_score >= 60:
            strengths.append(f"Market breadth is {breadth.get('breadth_status', 'supportive').lower()}")
        elif breadth_score < 40:
            concerns.append(f"Market breadth is {breadth.get('breadth_status', 'weak').lower()}")

    if sentiment.get("fear_greed_label") == "Extreme Greed":
        concerns.append("Market sentiment is at extreme greed, increasing chase risk")
    elif sentiment.get("fear_greed_label") in {"Fear", "Extreme Fear"}:
        concerns.append("Market sentiment remains defensive")

    if rs_score is not None:
        if rs_score >= 70:
            strengths.append(f"Stock relative strength is strong ({rs_score:.0f}/100)")
        elif rs_score < 45:
            concerns.append(f"Stock relative strength is weak ({rs_score:.0f}/100)")

    sector_name = relative_strength.get("sector_name")
    sector_etf = relative_strength.get("sector_etf")
    for item in sectors.get("rankings", []):
        if item.get("symbol") == sector_etf or item.get("sector") == sector_name:
            sector_score = _number(item.get("score"))
            if sector_score is not None and sector_score >= 70:
                strengths.append(f"Its sector is strong ({item.get('sector')} {sector_score:.0f}/100)")
            elif sector_score is not None and sector_score < 40:
                concerns.append(f"Its sector is weak ({item.get('sector')} {sector_score:.0f}/100)")
            break

    news_summary = news_context.get("summary", {})
    overall_news = news_summary.get("overall_sentiment")
    high_impact_news = news_summary.get("high_impact", 0)
    if overall_news == "Bullish":
        strengths.append("Recent verified headlines lean bullish")
    elif overall_news == "Bearish":
        concerns.append("Recent verified headlines lean bearish")
    elif overall_news == "Mixed":
        concerns.append("Recent verified headlines are mixed")
    if high_impact_news:
        concerns.append(f"{high_impact_news} recent high-impact headline(s) require review")

    if confidence >= 82 and dee_fit >= 80 and (risk_reward or 0) >= 1.5:
        decision = "Entry Ready"
    elif confidence >= 72 and dee_fit >= 70:
        decision = "Bullish Watch"
    elif confidence >= 60:
        decision = "Wait for Confirmation"
    else:
        decision = "Avoid"

    setup = stock.get("Setup", "Unclassified")
    summary = (
        f"{decision}: the {setup} setup has a technical score of {score:.0f}, "
        f"Dee Fit of {dee_fit:.0f}, and Momo Confidence of {confidence:.0f}%."
    )

    confirmation = []
    if rvol is not None and rvol < 1:
        confirmation.append("RVOL improves to at least 1.0")
    confirmation.append("Price holds above the selected structural support")
    confirmation.append("Momentum remains constructive without becoming extended")

    invalidation = []
    risk_reference = _number(stock.get("Risk Reference"))
    if risk_reference is not None:
        invalidation.append(f"A decisive close below ${risk_reference:.2f}")
    invalidation.append("Breakdown of the current EMA21 structure")
    invalidation.append("Material deterioration in volume or momentum")

    return {
        "decision": decision,
        "summary": summary,
        "strengths": strengths[:5],
        "concerns": concerns[:5],
        "confirmation": confirmation[:4],
        "invalidation": invalidation[:4],
    }


def _stock_payload(
    stock: Any,
    market_context: dict[str, Any] | None = None,
    relative_strength: dict[str, Any] | None = None,
    news_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    keys = [
        "Symbol",
        "Grade",
        "Setup",
        "Close",
        "Score",
        "Dee Fit",
        "Momo Score",
        "Momo Confidence",
        "Confidence Rating",
        "ATR %",
        "RVOL",
        "Distance EMA21 %",
        "Reasons",
        "Trend Confidence",
        "Location Confidence",
        "Momentum Confidence",
        "Volume Confidence",
        "Opportunity Confidence",
        "Risk Confidence",
        "Structure Confidence",
        "Support 1",
        "Support 1 Quality",
        "Support 1 Touches",
        "Support 2",
        "Support 2 Quality",
        "Support 2 Touches",
        "Resistance 1",
        "Resistance 1 Quality",
        "Resistance 1 Touches",
        "Resistance 2",
        "Resistance 2 Quality",
        "Resistance 2 Touches",
        "Resistance 3",
        "Resistance 3 Quality",
        "Resistance 3 Touches",
        "Risk Reference",
        "Reward Reference",
        "Risk Reward",
        "Risk Reward Status",
        "T1",
        "T1 Upside %",
        "T1 R",
        "T2",
        "T2 Upside %",
        "T2 R",
        "T3",
        "T3 Upside %",
        "T3 R",
    ]

    payload = {}

    for key in keys:
        value = stock.get(key)

        if _valid_number(value):
            payload[key] = round(float(value), 4)
        elif value is None:
            payload[key] = None
        else:
            payload[key] = str(value)

    payload["Market Context"] = market_context or None
    payload["Relative Strength"] = relative_strength or None
    payload["News Context"] = news_context or None

    return payload


def generate_ai_decision(
    api_key: str,
    stock: Any,
    market_context: dict[str, Any] | None = None,
    relative_strength: dict[str, Any] | None = None,
    news_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate an independent technical AI decision on demand."""
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from Streamlit secrets.")

    client = OpenAI(api_key=api_key)
    payload = _stock_payload(stock, market_context, relative_strength, news_context)

    system_prompt = """
You are the independent AI analyst inside MomoPro AI, a swing-trading decision-support application.
Analyze the supplied technical, structural, market, breadth, sentiment, sector, relative-strength, and verified news data.
Use only the supplied news context for catalysts. Do not claim access to options activity or other feeds that are not supplied. You may disagree with the rule-based Momo Engine. Be practical, cautious, and specific.
Do not promise outcomes or describe a trade as guaranteed. Use concise language suitable for a stock report.
The decision must be exactly one of: Entry Ready, Bullish Watch, Wait for Confirmation, Neutral, Avoid.
""".strip()

    user_prompt = (
        "Evaluate this swing-trade candidate and return the structured decision. "
        "Treat the current close as a reference, not an automatic entry.\n\n"
        + json.dumps(payload, indent=2)
    )

    response = client.responses.parse(
        model=MODEL,
        reasoning={"effort": "low"},
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text_format=AIStockDecision,
    )

    parsed = response.output_parsed

    if parsed is None:
        raise RuntimeError("The AI response did not contain a parsed decision.")

    return parsed.model_dump()

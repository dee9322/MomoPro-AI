"""Independent AI Research Workstation for MomoPro AI."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field

MODEL = "gpt-5.4-mini"


class ConfidenceComponent(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)
    weight: int = Field(ge=0, le=100)
    contribution: float
    reason: str


class AIResearchReport(BaseModel):
    executive_summary: str
    sentiment: str = Field(
        description="One of: Very Bullish, Bullish, Cautiously Bullish, Neutral, Cautiously Bearish, Bearish, Very Bearish"
    )
    confidence: int = Field(ge=0, le=100)
    conviction: str = Field(description="One of: Low, Moderate, High")
    time_horizon: str
    risk_level: str = Field(description="One of: Low, Moderate, Elevated, High")
    final_rating: str = Field(
        description="One of: Strong Buy Candidate, Buy Candidate, Watch, Neutral, Avoid, Avoid Completely"
    )
    technical_analysis: str
    market_analysis: str
    news_catalyst_analysis: str
    smart_money_analysis: str
    trading_intelligence_analysis: str
    bull_case: list[str]
    bear_case: list[str]
    biggest_risks: list[str]
    confirmations: list[str]
    invalidations: list[str]
    blind_spots: list[str]
    momo_engine_comparison: str
    disagreement_reason: str
    confidence_breakdown: list[ConfidenceComponent]
    questions_to_ask_next: list[str]


def generate_research_report(
    api_key: str,
    symbol: str,
    stock_payload: dict[str, Any],
    momo_engine: dict[str, Any],
    market_context: dict[str, Any] | None = None,
    relative_strength: dict[str, Any] | None = None,
    news_context: dict[str, Any] | None = None,
    sec_filings: list[dict[str, Any]] | None = None,
    fda_records: list[dict[str, Any]] | None = None,
    smart_money_context: dict[str, Any] | None = None,
    trade_intelligence_context: dict[str, Any] | None = None,
    comparison_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a full independent research report from app evidence.

    The model is instructed to form its own opinion rather than merely mirror
    the deterministic Momo Engine.
    """
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from Streamlit secrets.")

    evidence = {
        "symbol": symbol,
        "stock": stock_payload,
        "momo_engine": momo_engine,
        "market_context": market_context,
        "relative_strength": relative_strength,
        "news_context": news_context,
        "sec_filings": sec_filings or [],
        "fda_records": fda_records or [],
        "smart_money_context": smart_money_context,
        "trading_intelligence_context": trade_intelligence_context,
        "comparison_stock": comparison_payload,
    }

    system_prompt = """
You are the Independent AI Research Analyst inside MomoPro AI, a swing-trading research and decision-support platform.

Your job is NOT to repeat the Momo Engine. Review all supplied evidence, form your own independent sentiment, and explain where you agree or disagree with the deterministic engine. The user prefers momentum swing trades, especially fresh EMA21 reclaim/retest setups, usually lasting days to a few weeks. They avoid chasing stocks that are too extended and prefer logical support-based risk with asymmetric reward.

Rules:
- Use only supplied evidence. Never invent current news, filings, ownership, options, short-interest, prices, or chart facts.
- Treat missing data as missing, not neutral or zero.
- Separate verified facts from inferred behavior.
- Smart Money OHLCV accumulation is inferred, not proof of institutional orders.
- Indicative options data is delayed and not equivalent to institutional sweep flow.
- Treat the current close as a reference, not an automatic entry.
- Your final opinion may disagree with the Momo Engine.
- Be specific and practical, but never promise outcomes.
- Make the report useful to a swing trader, not a long-term investment analyst.
- Confidence must reflect both evidence strength and data completeness.
- Confidence breakdown contributions should approximately sum to the final confidence.
""".strip()

    user_prompt = (
        f"Create the complete independent AI research report for {symbol}. "
        "State your own conclusion after considering the Momo Engine, but do not defer to it.\n\n"
        + json.dumps(evidence, default=str, indent=2)
    )

    client = OpenAI(api_key=api_key)
    response = client.responses.parse(
        model=MODEL,
        reasoning={"effort": "medium"},
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text_format=AIResearchReport,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("The AI research response did not contain parsed output.")
    return parsed.model_dump()

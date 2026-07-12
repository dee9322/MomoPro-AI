"""Complete Independent AI Research Workstation for MomoPro AI."""

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


class ChecklistItem(BaseModel):
    item: str
    status: str = Field(description="Pass, Caution, Fail, or Unavailable")
    explanation: str


class AIResearchReport(BaseModel):
    executive_summary: str
    sentiment: str
    confidence: int = Field(ge=0, le=100)
    conviction: str
    time_horizon: str
    risk_level: str
    final_rating: str
    user_strategy_fit: str
    independent_action: str = Field(
        description="Buy Now, Wait for Pullback, Wait for Confirmation, Watchlist, Reduce Size, or Pass"
    )
    action_plan: str
    technical_analysis: str
    market_analysis: str
    news_catalyst_analysis: str
    earnings_filing_analysis: str
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
    bull_analyst_argument: str
    bear_analyst_argument: str
    debate_winner: str
    debate_reason: str
    evidence_quality: str
    missing_evidence: list[str]
    confidence_breakdown: list[ConfidenceComponent]
    readiness_checklist: list[ChecklistItem]
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
You are the Independent AI Research Analyst inside MomoPro AI.

Your job is to form your own evidence-based swing-trading opinion. Do not merely repeat or endorse the deterministic Momo Engine. Compare your conclusion with it and clearly explain agreement or disagreement.

The user prefers:
- momentum swing trades lasting days to roughly 2–3 weeks;
- fresh EMA21 reclaim/retest and continuation setups;
- entries near logical support rather than chasing;
- EMA21/EMA50/EMA200, RSI, MACD, RVOL, ATR, structure and multiple targets;
- strong reward/risk and clear invalidation;
- A/A+ quality over quantity.

Rules:
- Use only supplied current evidence, including on-demand comparison research.
- Never invent current prices, news, filings, ownership, options, short interest, earnings dates, chart patterns, or provider results.
- Missing evidence is missing, not neutral and not zero.
- Clearly separate verified provider facts, deterministic calculations, inferred behavior, and your interpretation.
- Smart Money accumulation inferred from OHLCV is not proof of institutional orders.
- Indicative options data is delayed and is not verified sweep flow.
- A good company is not automatically a good entry.
- The current close is only a reference.
- If comparison evidence exists, make a direct side-by-side swing-trade judgment.
- Your independent action must be practical: Buy Now, Wait for Pullback, Wait for Confirmation, Watchlist, Reduce Size, or Pass.
- Confidence must decline when evidence is incomplete or contradictory.
- The confidence breakdown must be transparent and approximately reconcile to final confidence.
- Write like an experienced swing trader, not a generic chatbot.
- Never guarantee outcomes.
""".strip()

    user_prompt = (
        f"Create the complete independent AI research report for {symbol}. "
        "Give your own sentiment, debate the strongest bull and bear cases, state what you would do, "
        "explain how well the setup fits the user's strategy, and identify missing evidence.\n\n"
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

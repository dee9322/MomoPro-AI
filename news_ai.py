from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field


MODEL = "gpt-5.4-mini"


class NewsCatalystAnalysis(BaseModel):
    overall_sentiment: str
    impact: str
    catalyst_summary: str
    bullish_factors: list[str]
    bearish_factors: list[str]
    near_term_watch: list[str]
    confidence: int = Field(ge=0, le=100)


def analyze_news(
    api_key: str,
    symbol: str,
    news_items: list[dict[str, Any]],
    filings: list[dict[str, Any]] | None = None,
    fda_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from Streamlit secrets.")

    compact_news = [
        {
            "headline": item.get("headline"),
            "summary": item.get("summary"),
            "sentiment": item.get("sentiment"),
            "impact": item.get("impact"),
            "category": item.get("category"),
            "created_at": str(item.get("created_at")),
        }
        for item in news_items[:20]
    ]

    payload = {
        "symbol": symbol,
        "news": compact_news,
        "sec_filings": (filings or [])[:10],
        "fda_enforcement": (fda_records or [])[:8],
    }

    client = OpenAI(api_key=api_key)
    response = client.responses.parse(
        model=MODEL,
        reasoning={"effort": "low"},
        input=[
            {
                "role": "system",
                "content": (
                    "You are the News & Catalyst analyst inside MomoPro AI. "
                    "Use only the supplied verified headlines, SEC filing metadata, and FDA records. "
                    "Separate facts from interpretation. Never promise price direction. "
                    "Flag dilution, investigations, recalls, weak guidance, earnings risk, and major catalysts."
                ),
            },
            {
                "role": "user",
                "content": "Analyze this news package:\n" + json.dumps(payload, indent=2),
            },
        ],
        text_format=NewsCatalystAnalysis,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("The AI response did not contain parsed news analysis.")
    return parsed.model_dump()

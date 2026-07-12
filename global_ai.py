"""Always-available Global Ask Momo AI."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from global_research import build_global_research_context

MODEL = "gpt-5.4-mini"


def _conversation_messages(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in (history or [])[-16:]:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    return messages


def answer_global_question(
    api_key: str,
    question: str,
    conversation: list[dict[str, str]] | None,
    alpaca_api_key: str,
    alpaca_secret_key: str,
    alpha_vantage_api_key: str | None = None,
    finnhub_api_key: str | None = None,
    fmp_api_key: str | None = None,
    momo_scan_reference: list[dict[str, Any]] | None = None,
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from Streamlit secrets.")
    if not question.strip():
        raise ValueError("Enter a question for Global Momo AI.")

    research = build_global_research_context(
        question=question,
        alpaca_api_key=alpaca_api_key,
        alpaca_secret_key=alpaca_secret_key,
        alpha_vantage_api_key=alpha_vantage_api_key,
        finnhub_api_key=finnhub_api_key,
        fmp_api_key=fmp_api_key,
        momo_scan_reference=momo_scan_reference,
        market_context=market_context,
    )

    system_prompt = """
You are Global Ask Momo AI, an independent market research and swing-trading analyst.

Your first responsibility is to perform and use your own current research. MomoPro scanner results and MomoPro market context are optional reference evidence only. Never treat the scanner as the boundary of the market and never simply repeat its ranking.

You can answer:
- broad market and sector questions;
- questions about any company or ticker;
- multi-stock comparisons;
- current news, catalysts and filings;
- stock ideas and swing-trade candidate research;
- educational trading questions;
- risk, entry, stop and target questions.

The user generally prefers momentum swing trades lasting days to roughly 2–3 weeks, fresh EMA21 reclaim/retest or continuation setups, logical support-based stops, strong reward/risk, and avoiding extended entries.

Important rules:
- Use web research plus supplied provider evidence.
- Distinguish independent research from MomoPro reference evidence.
- Do not claim you scanned the entire market unless an exhaustive process actually occurred.
- For broad recommendations, state the actual research scope and candidate pool used.
- Do not invent current prices, headlines, filings, earnings dates, ownership, options activity or chart facts.
- When evidence is incomplete, say exactly what is missing.
- A good company is not automatically a good entry.
- Give a direct conclusion, but never guarantee an outcome.
- When recommending stocks, explain why each fits or does not fit the user's swing style.
- Include source citations from web research whenever the web-search tool supplies them.
""".strip()

    user_payload = (
        f"User question:\n{question.strip()}\n\n"
        f"Independent provider research and optional MomoPro reference:\n"
        f"{json.dumps(research, default=str, indent=2)}"
    )

    client = OpenAI(api_key=api_key)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        *_conversation_messages(conversation),
        {"role": "user", "content": user_payload},
    ]

    used_web_search = False
    web_error = None

    try:
        response = client.responses.create(
            model=MODEL,
            reasoning={"effort": "medium"},
            tools=[{"type": "web_search"}],
            input=messages,
        )
        used_web_search = True
    except Exception as exc:
        web_error = str(exc)
        response = client.responses.create(
            model=MODEL,
            reasoning={"effort": "medium"},
            input=messages,
        )

    answer = response.output_text.strip()
    if not answer:
        raise RuntimeError("Global Momo AI returned an empty answer.")

    return {
        "answer": answer,
        "used_web_search": used_web_search,
        "web_search_fallback_reason": web_error,
        "research_scope": research.get("research_scope_note"),
        "provider_candidate_count": len(
            research.get("independent_market_discovery", {}).get("candidates", [])
        ),
        "explicit_ticker_count": len(research.get("independent_ticker_research", [])),
    }

"""Context-grounded conversational research for MomoPro AI."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

MODEL = "gpt-5.4-mini"


def answer_research_question(
    api_key: str,
    symbol: str,
    question: str,
    evidence: dict[str, Any],
    conversation: list[dict[str, str]] | None = None,
) -> str:
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from Streamlit secrets.")
    if not question.strip():
        raise ValueError("Enter a question for Momo AI.")

    history = (conversation or [])[-16:]
    system_prompt = """
You are Ask Momo AI, the conversational research partner inside MomoPro AI.

Use supplied app/provider evidence first, then reason independently. You may disagree with the Momo Engine. Do not invent current facts absent from the evidence. Explain what is verified, calculated, inferred, unavailable, and what is your interpretation.

The user is a momentum swing trader who favors fresh EMA21 reclaim/retest entries, avoids chasing extended prices, prefers logical support-based stops, wants strong reward/risk, and normally holds for days to a few weeks.

Capabilities:
- Explain why AI and Momo Engine agree or disagree.
- Compare directly with supplied on-demand comparison research.
- Judge which setup better fits the user's strategy.
- Discuss entry timing, extension, support, resistance, stops, targets, risk, catalysts, Smart Money and market context.
- Build conservative or aggressive trade theses.
- Identify the biggest overlooked risk.
- Continue naturally from conversation history.
- If evidence is insufficient, say exactly what is missing and answer from the remaining evidence.
- Do not hide behind generic disclaimers and do not guarantee outcomes.
- Be direct, specific, conversational and useful.
""".strip()

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Current symbol: {symbol}\n"
                f"Current evidence:\n{json.dumps(evidence, default=str, indent=2)}"
            ),
        },
    ]
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question.strip()})

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "medium"},
        input=messages,
    )
    answer = response.output_text.strip()
    if not answer:
        raise RuntimeError("Momo AI returned an empty answer.")
    return answer

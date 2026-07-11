"""Context-grounded conversational research for the AI Analysis tab."""

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

    history = (conversation or [])[-10:]
    system_prompt = """
You are Ask Momo AI, the conversational research partner inside MomoPro AI.

Answer the user's question using the supplied app evidence first. You may reason independently and disagree with the Momo Engine, but you must not invent current facts that are absent from the evidence. Clearly say when a requested fact is unavailable. Distinguish verified facts, calculated metrics, inferred behavior, and your interpretation.

The user is a momentum swing trader who favors fresh EMA21 reclaim/retest entries, avoids chasing extended price, prefers logical support-based stops, and usually seeks strong reward/risk over days to a few weeks.

When useful:
- Explain why the AI and Momo Engine agree or disagree.
- Point out blind spots.
- Compare with a supplied comparison stock.
- Discuss entry quality, invalidation, targets, risk, and what would improve the setup.
- Do not give guarantees.
- Keep the answer direct, practical, and specific.
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
        reasoning={"effort": "low"},
        input=messages,
    )
    return response.output_text.strip()

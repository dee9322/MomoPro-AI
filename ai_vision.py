"""Screenshot and chart analysis for MomoPro AI."""

from __future__ import annotations

import base64
import json
from typing import Any

from openai import OpenAI

MODEL = "gpt-5.4-mini"


def analyze_chart_image(
    api_key: str,
    symbol: str,
    image_bytes: bytes,
    mime_type: str,
    question: str,
    evidence: dict[str, Any] | None = None,
) -> str:
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from Streamlit secrets.")
    if not image_bytes:
        raise ValueError("Upload a chart or screenshot first.")

    encoded = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"

    system_prompt = """
You are the chart and screenshot analyst inside MomoPro AI.

Analyze the visible image carefully and combine it with the supplied MomoPro evidence. Do not claim to see details that are unreadable. Distinguish what is visibly observed from what comes from app evidence. Focus on swing-trading structure: trend, EMA interaction, support/resistance, volume, extension, pattern quality, entry timing, invalidation, risk and what confirmation is still needed.

Never guarantee outcomes. If the screenshot does not show enough information, say what is missing.
""".strip()

    evidence_text = json.dumps(evidence or {}, default=str, indent=2)
    prompt = (
        f"Symbol: {symbol}\n"
        f"User question: {question or 'Analyze this chart for a swing trade.'}\n"
        f"App evidence:\n{evidence_text}"
    )

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "medium"},
        input=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            },
        ],
    )
    answer = response.output_text.strip()
    if not answer:
        raise RuntimeError("The screenshot analysis returned an empty answer.")
    return answer

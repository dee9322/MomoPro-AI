"""Shared formatting and small presentation helpers for MomoPro AI."""
from __future__ import annotations

import math
from typing import Any

import pandas as pd


def valid_value(value: Any) -> bool:
    try:
        return value is not None and not pd.isna(value) and (
            not isinstance(value, float) or math.isfinite(value)
        )
    except (TypeError, ValueError):
        return value is not None


def money_text(value: Any) -> str:
    return f"${float(value):.2f}" if valid_value(value) else "—"


def percent_text(value: Any) -> str:
    return f"{float(value):.2f}%" if valid_value(value) else "—"


def r_text(value: Any) -> str:
    return f"{float(value):.2f}R" if valid_value(value) else "—"


def compact_number(value: Any) -> str:
    if not valid_value(value):
        return "—"
    number = float(value)
    absolute = abs(number)
    if absolute >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    if absolute >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{number:,.0f}"


def reaction_text(quality: Any, touches: Any) -> str | None:
    if not valid_value(touches):
        return None
    quality_text = str(quality) if valid_value(quality) else "Unrated"
    touch_count = int(float(touches))
    reaction_word = "reaction" if touch_count == 1 else "reactions"
    return f"{quality_text} · {touch_count} confirmed {reaction_word}"

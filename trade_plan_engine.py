from __future__ import annotations

import math
from typing import Any, Mapping

from analysis_models import CanonicalTradePlan


def _valid(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _num(value: Any) -> float | None:
    return float(value) if _valid(value) else None


def _pick(mapping: Mapping[str, Any] | None, *keys: str) -> Any:
    mapping = mapping or {}
    for key in keys:
        value = mapping.get(key)
        if _valid(value):
            return value
    return None


def _target_prices(trading_intelligence: Mapping[str, Any] | None) -> list[float | None]:
    rows = ((trading_intelligence or {}).get("targets") or {}).get("targets") or []
    prices: list[float | None] = []
    for row in rows[:3]:
        prices.append(_num((row or {}).get("price")))
    while len(prices) < 3:
        prices.append(None)
    return prices


def build_canonical_trade_plan(
    stock: Mapping[str, Any] | None,
    trading_intelligence: Mapping[str, Any] | None = None,
) -> CanonicalTradePlan:
    """Resolve one official plan without changing any underlying engine.

    Priority is intentionally explicit: advanced Trading Intelligence values are
    used when available; scanner/Stock Report values remain the safe fallback.
    All downstream screens should consume this resolved plan instead of repeating
    their own fallback rules.
    """
    stock = stock or {}
    ti = trading_intelligence or {}
    entry_quality = ti.get("entry_quality") or {}
    stops = ti.get("adaptive_stops") or {}
    target_prices = _target_prices(ti)

    reference_entry = _num(_pick(
        entry_quality,
        "reference_entry", "entry", "balanced_entry", "suggested_entry",
    )) or _num(_pick(stock, "Reference Entry", "Close", "Price"))

    entry_low = _num(_pick(entry_quality, "entry_low", "zone_low", "entry_zone_low"))
    entry_high = _num(_pick(entry_quality, "entry_high", "zone_high", "entry_zone_high"))
    if entry_low is None:
        entry_low = reference_entry
    if entry_high is None:
        entry_high = reference_entry

    stop = _num(_pick(stops, "standard", "recommended", "balanced"))
    if stop is None:
        stop = _num(_pick(stock, "Risk Reference", "Stop"))

    t1 = target_prices[0] or _num(_pick(stock, "T1", "Reward Reference"))
    t2 = target_prices[1] or _num(_pick(stock, "T2"))
    t3 = target_prices[2] or _num(_pick(stock, "T3"))
    support = _num(_pick(stock, "Support", "Support 1", "Risk Reference"))
    resistance = _num(_pick(stock, "Resistance", "Resistance 1", "Reward Reference"))

    return CanonicalTradePlan(
        entry_low=entry_low,
        entry_high=entry_high,
        reference_entry=reference_entry,
        stop=stop,
        t1=t1,
        t2=t2,
        t3=t3,
        support=support,
        resistance=resistance,
        risk_reward=_num(_pick(stock, "Risk Reward")),
        t1_r=_num(_pick(stock, "T1 R")),
        t2_r=_num(_pick(stock, "T2 R")),
        t3_r=_num(_pick(stock, "T3 R")),
    )

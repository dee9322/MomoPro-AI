from __future__ import annotations

import math
from typing import Any, Mapping

from analysis_models import MomoAnalysis
from trade_plan_engine import build_canonical_trade_plan


def _valid(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _num(value: Any) -> float | None:
    return float(value) if _valid(value) else None


def _first(mapping: Mapping[str, Any] | None, *keys: str, default: Any = None) -> Any:
    mapping = mapping or {}
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def build_canonical_analysis(
    symbol: str,
    stock: Mapping[str, Any] | None,
    *,
    trading_intelligence: Mapping[str, Any] | None = None,
    market_context: Mapping[str, Any] | None = None,
    news_context: Mapping[str, Any] | None = None,
    smart_money_context: Mapping[str, Any] | None = None,
    ai_report: Mapping[str, Any] | None = None,
    learning_context: Mapping[str, Any] | None = None,
    opportunity_score: float | None = None,
    thesis: str = "",
    invalidation: str = "",
) -> MomoAnalysis:
    stock = dict(stock or {})
    ti = dict(trading_intelligence or {})
    ai = dict(ai_report or {})
    pattern = ti.get("pattern") or {}
    entry_quality = ti.get("entry_quality") or {}
    plan = build_canonical_trade_plan(stock, ti)

    setup = str(
        _first(pattern, "primary_pattern", default="")
        or _first(stock, "Setup", "Setup Type", default="")
    )
    grade = str(
        _first(entry_quality, "grade", default="")
        or _first(stock, "Grade", default="")
    )

    reasons = stock.get("Reasons") or stock.get("Why") or []
    if isinstance(reasons, str):
        reasons = [part.strip() for part in reasons.split("|") if part.strip()]

    warnings = entry_quality.get("warnings") or []
    if isinstance(warnings, str):
        warnings = [part.strip() for part in warnings.split("|") if part.strip()]

    return MomoAnalysis(
        symbol=str(symbol or stock.get("Symbol") or "").upper().strip(),
        data_freshness={
            "scanner": stock.get("Scanned At") or stock.get("Timestamp"),
            "trading_intelligence": ti.get("generated_at"),
            "ai_research": ai.get("generated_at") or ai.get("timestamp"),
        },
        identity={
            "company": _first(stock, "Company", "Name", default=""),
            "sector": _first(stock, "Sector", default=""),
            "industry": _first(stock, "Industry", default=""),
        },
        technicals=stock,
        market_context=dict(market_context or {}),
        news_context=dict(news_context or {}),
        smart_money_context=dict(smart_money_context or {}),
        trading_intelligence=ti,
        ai_research=ai,
        learning_context=dict(learning_context or {}),
        setup=setup,
        grade=grade,
        momo_score=_num(_first(stock, "Momo Score")),
        momo_confidence=_num(_first(stock, "Momo Confidence")),
        opportunity_score=_num(
            opportunity_score
            if opportunity_score is not None
            else _first(stock, "Opportunity Score")
        ),
        ai_confidence=_num(_first(ai, "confidence", "ai_confidence")),
        ai_action=str(
            _first(ai, "independent_action", "action", "recommendation", default="")
        ),
        thesis=thesis or str(_first(ai, "trade_thesis", "thesis", default="")),
        invalidation=invalidation
        or str(_first(ai, "invalidation", "thesis_invalidation", default="")),
        plan=plan,
        reasons=list(reasons or []),
        warnings=list(warnings or []),
    )


def planner_prefill(analysis: MomoAnalysis | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(analysis, MomoAnalysis):
        payload = analysis.to_dict()
    else:
        payload = dict(analysis or {})

    plan = payload.get("plan") or {}
    symbol = str(payload.get("symbol") or "").upper().strip()
    generated_at = str(payload.get("generated_at") or "")

    return {
        "symbol": symbol,
        "entry": plan.get("reference_entry") or plan.get("entry_low"),
        "entry_low": plan.get("entry_low"),
        "entry_high": plan.get("entry_high"),
        "stop": plan.get("stop"),
        "t1": plan.get("t1"),
        "t2": plan.get("t2"),
        "t3": plan.get("t3"),
        "notes": payload.get("thesis", ""),
        "canonical_analysis_id": f"{symbol}:{generated_at}",
    }

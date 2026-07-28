from __future__ import annotations

from datetime import datetime

from trade_models import TradeRecord


def _dt(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def plan_completeness(trade: TradeRecord) -> float:
    fields = [
        trade.entry_price, trade.shares, trade.initial_stop, trade.t1, trade.t2,
        trade.t3, trade.setup, trade.thesis, trade.invalidation,
    ]
    completed = sum(value not in (None, "", 0, 0.0) for value in fields)
    return round(100 * completed / len(fields), 1)


def _confidence(evidence: dict) -> float:
    try:
        return max(0.0, min(100.0, float(evidence.get("confidence") or 0)))
    except Exception:
        return 0.0


def _intelligence_score(trade: TradeRecord, mode: str) -> float:
    by_type = {str(item.get("evidence_type") or ""): item for item in trade.evidence}
    score = 0.0

    if "broker_execution" in by_type:
        score += 35 * (_confidence(by_type["broker_execution"]) / 100)
    if "protective_stop" in by_type:
        score += 20 * (_confidence(by_type["protective_stop"]) / 100)
    if "historical_daily_chart" in by_type:
        score += 20 * (_confidence(by_type["historical_daily_chart"]) / 100)
    if "historical_intraday_chart" in by_type:
        score += 10 * (_confidence(by_type["historical_intraday_chart"]) / 100)
    if "official_plan" in by_type or trade.plan_id:
        score += 35

    timeline_count = len(trade.timeline or [])
    if timeline_count:
        score += min(15, 5 + timeline_count * 2)

    if mode == "partial_plan":
        score = max(score, 60)
    elif mode == "verified_plan":
        score = max(score, 88)
    elif mode == "live_managed":
        score = max(score, 94)
    elif mode == "historical_reconstruction":
        score = max(score, 50)
    elif mode == "imported_only":
        score = min(score, 45)
    return round(min(100, score), 1)


def classify_trade(trade: TradeRecord) -> TradeRecord:
    completeness = max(float(trade.plan_completeness or 0), plan_completeness(trade) if trade.plan_id else 0)
    trade.plan_completeness = completeness
    entry_at = _dt(trade.entry_date)
    plan_created_at = _dt(trade.plan_created_at)
    pre_entry_plan = bool(trade.plan_id and plan_created_at and entry_at and plan_created_at <= entry_at)
    actively_managed = bool(trade.updates and pre_entry_plan)

    if actively_managed:
        mode = "live_managed"
        reason = "A pre-entry Official Plan exists and management events were recorded."
    elif pre_entry_plan and completeness >= 75:
        mode = "verified_plan"
        reason = "A sufficiently complete Official Plan was saved before the first entry."
    elif pre_entry_plan:
        mode = "partial_plan"
        reason = "A pre-entry plan exists, but some planning evidence is incomplete."
    elif trade.broker_execution_ids:
        mode = "historical_reconstruction"
        reason = "Broker executions exist without a qualifying pre-entry Official Plan."
    else:
        mode = "imported_only"
        reason = "There is not enough verified planning or broker evidence for reconstruction."

    trade.review_mode = mode
    trade.classification_reason = reason
    trade.intelligence_score = _intelligence_score(trade, mode)
    return trade


def classification_label(mode: str) -> str:
    return {
        "live_managed": "Live Managed",
        "verified_plan": "Verified Plan",
        "partial_plan": "Partial Plan",
        "historical_reconstruction": "Historical Reconstruction",
        "imported_only": "Imported Only",
    }.get(str(mode or "").strip().lower(), "Imported Only")

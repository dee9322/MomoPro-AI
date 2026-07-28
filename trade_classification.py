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
        trade.entry_price,
        trade.shares,
        trade.initial_stop,
        trade.t1,
        trade.t2,
        trade.t3,
        trade.setup,
        trade.thesis,
        trade.invalidation,
    ]
    completed = sum(value not in (None, "", 0, 0.0) for value in fields)
    return round(100 * completed / len(fields), 1)


def classify_trade(trade: TradeRecord) -> TradeRecord:
    completeness = max(
        float(trade.plan_completeness or 0),
        plan_completeness(trade) if trade.plan_id else 0,
    )
    trade.plan_completeness = completeness

    entry_at = _dt(trade.entry_date)
    plan_created_at = _dt(trade.plan_created_at)
    pre_entry_plan = bool(
        trade.plan_id
        and plan_created_at
        and entry_at
        and plan_created_at <= entry_at
    )
    actively_managed = bool(trade.updates and pre_entry_plan)

    if actively_managed:
        mode = "live_managed"
        reason = (
            "A pre-entry Official Plan exists and management events were recorded."
        )
    elif pre_entry_plan and completeness >= 75:
        mode = "verified_plan"
        reason = (
            "A sufficiently complete Official Plan was saved before the first entry."
        )
    elif pre_entry_plan:
        mode = "partial_plan"
        reason = (
            "A pre-entry plan exists, but some planning evidence is incomplete."
        )
    elif trade.broker_execution_ids:
        mode = "historical_reconstruction"
        reason = (
            "Broker executions exist without a qualifying pre-entry Official Plan."
        )
    else:
        mode = "imported_only"
        reason = (
            "There is not enough verified planning or broker evidence for reconstruction."
        )

    trade.review_mode = mode
    trade.classification_reason = reason

    base_score = {
        "live_managed": 98,
        "verified_plan": 94,
        "partial_plan": 80,
        "historical_reconstruction": 65,
        "imported_only": 35,
    }[mode]
    evidence_bonus = min(len(trade.evidence) * 2, 10)
    trade.intelligence_score = min(100, base_score + evidence_bonus)
    return trade


def classification_label(mode: str) -> str:
    labels = {
        "live_managed": "Live Managed",
        "verified_plan": "Verified Plan",
        "partial_plan": "Partial Plan",
        "historical_reconstruction": "Historical Reconstruction",
        "imported_only": "Imported Only",
    }
    return labels.get(str(mode or "").strip().lower(), "Imported Only")

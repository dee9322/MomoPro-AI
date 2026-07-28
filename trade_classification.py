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


def _confidence(evidence: dict) -> float:
    try:
        return max(0.0, min(100.0, float(evidence.get("confidence") or 0)))
    except Exception:
        return 0.0


def _best_evidence_by_type(trade: TradeRecord) -> dict[str, dict]:
    """Keep the strongest item of each evidence type.

    This makes the score deterministic and prevents duplicate rows from inflating it.
    Adding a stronger evidence item can only maintain or increase the score.
    """
    strongest: dict[str, dict] = {}
    for item in trade.evidence or []:
        evidence_type = str(item.get("evidence_type") or "").strip()
        if not evidence_type:
            continue
        if evidence_type not in strongest or _confidence(item) > _confidence(strongest[evidence_type]):
            strongest[evidence_type] = item
    return strongest


def _timeline_score(trade: TradeRecord) -> float:
    event_types = {str(item.get("event_type") or "") for item in (trade.timeline or [])}
    score = 0.0
    if "execution" in event_types:
        score += 4.0
    if event_types.intersection({"order_observed", "order_submitted", "order_cancelled"}):
        score += 3.0
    if "plan" in event_types:
        score += 2.0
    if "management" in event_types:
        score += 1.0
    return min(10.0, score)


def _intelligence_score(trade: TradeRecord, mode: str) -> float:
    """Measure how complete and trustworthy the trade record is.

    This is not a trade-quality grade. Every component is positive and fixed, so
    newly discovered evidence cannot make an existing trade score lower.
    """
    by_type = _best_evidence_by_type(trade)
    weights = {
        "broker_execution": 30.0,
        "protective_stop": 15.0,
        "historical_daily_chart": 18.0,
        "historical_intraday_chart": 17.0,
        "official_plan": 20.0,
    }

    score = sum(
        weight * (_confidence(by_type[evidence_type]) / 100.0)
        for evidence_type, weight in weights.items()
        if evidence_type in by_type
    )
    score += _timeline_score(trade)

    # Classification floors describe the minimum trust level supported by that
    # review mode. They never subtract evidence already earned.
    floors = {
        "live_managed": 94.0,
        "verified_plan": 88.0,
        "partial_plan": 62.0,
        "historical_reconstruction": 38.0,
        "imported_only": 0.0,
    }
    score = max(score, floors.get(mode, 0.0))
    if mode == "imported_only":
        score = min(score, 45.0)
    return round(min(100.0, score), 1)


def classify_trade(trade: TradeRecord) -> TradeRecord:
    completeness = max(
        float(trade.plan_completeness or 0),
        plan_completeness(trade) if trade.plan_id else 0,
    )
    trade.plan_completeness = completeness
    entry_at = _dt(trade.entry_date)
    plan_created_at = _dt(trade.plan_created_at)
    pre_entry_plan = bool(
        trade.plan_id and plan_created_at and entry_at and plan_created_at <= entry_at
    )
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

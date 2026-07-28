from __future__ import annotations


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _reconstruction_confidence(reconstruction: dict) -> float:
    explicit = reconstruction.get("evidence_confidence")
    if explicit not in (None, "", 0, 0.0):
        return max(0.0, min(100.0, _number(explicit)))
    if reconstruction.get("intraday_execution_context"):
        return 96.0
    if reconstruction.get("daily_context") or reconstruction.get("entry_context"):
        return 78.0
    return 0.0


def _stop_details(stops):
    ordered = sorted(
        stops,
        key=lambda order: (
            order.submitted_at
            or order.created_at
            or order.cancelled_at
            or order.updated_at
            or order.synced_at
            or ""
        ),
    )
    prices = [
        float(order.stop_price or order.limit_price or 0)
        for order in ordered
        if (order.stop_price or order.limit_price)
    ]
    return {
        "orders": [
            {
                "order_id": order.order_id,
                "stop_price": order.stop_price or order.limit_price,
                "status": order.status,
                "purpose": order.purpose,
                "submitted_at": order.submitted_at or order.created_at,
                "cancelled_at": order.cancelled_at,
                "updated_at": order.updated_at,
                "observed_by_sync_at": order.synced_at,
            }
            for order in ordered
        ],
        "initial_stop": prices[0] if prices else None,
        "final_stop": prices[-1] if prices else None,
        "stop_changes": len(set(prices)),
    }


def refresh_trade_evidence(trades, orders, executions):
    """Rebuild evidence from source records without scoring the trade yet.

    Classification is intentionally performed only after the timeline is rebuilt.
    This avoids stale Evidence Item counts and stale Intelligence Scores.
    """
    for trade in trades:
        evidence: list[dict] = []

        if trade.plan_id:
            evidence.append({
                "evidence_type": "official_plan",
                "label": "Official Plan snapshot",
                "source": "MomoPro AI",
                "observed_at": trade.plan_created_at or trade.created_at,
                "confidence": 100,
                "details": {
                    "plan_id": trade.plan_id,
                    "completeness": trade.plan_completeness,
                },
            })

        matched_executions = [
            execution
            for execution in executions
            if execution.matched_trade_id == trade.id
        ]
        if matched_executions:
            evidence.append({
                "evidence_type": "broker_execution",
                "label": f"{len(matched_executions)} broker execution(s)",
                "source": "Webull",
                "observed_at": max(execution.executed_at for execution in matched_executions),
                "confidence": 100,
                "details": {
                    "execution_ids": [
                        execution.execution_id for execution in matched_executions
                    ]
                },
            })

        matched_orders = [
            order for order in orders if order.matched_trade_id == trade.id
        ]
        stops = [
            order for order in matched_orders if "Stop" in str(order.purpose or "")
        ]
        if stops:
            details = _stop_details(stops)
            observed_times = [
                order.cancelled_at
                or order.updated_at
                or order.submitted_at
                or order.created_at
                or order.synced_at
                for order in stops
                if (
                    order.cancelled_at
                    or order.updated_at
                    or order.submitted_at
                    or order.created_at
                    or order.synced_at
                )
            ]
            evidence.append({
                "evidence_type": "protective_stop",
                "label": f"{len(stops)} protective-stop order(s)",
                "source": "Webull",
                "observed_at": max(observed_times) if observed_times else "Timestamp unavailable",
                "confidence": max(_number(order.purpose_confidence) for order in stops),
                "details": details,
            })

        reconstruction = trade.reconstruction or {}
        if reconstruction:
            confidence = _reconstruction_confidence(reconstruction)
            daily_context = (
                reconstruction.get("daily_context")
                or reconstruction.get("entry_context")
                or {}
            )
            if daily_context:
                evidence.append({
                    "evidence_type": "historical_daily_chart",
                    "label": "Historical daily setup context",
                    "source": "Alpaca / MomoPro AI",
                    "observed_at": (
                        reconstruction.get("daily_context_as_of") or trade.entry_date
                    ),
                    "confidence": min(confidence, 92) if confidence else 78,
                    "details": {
                        "daily_as_of": reconstruction.get("daily_context_as_of"),
                        "hindsight_guard": reconstruction.get("hindsight_guard"),
                    },
                })

            intraday_context = reconstruction.get("intraday_execution_context") or {}
            if intraday_context:
                evidence.append({
                    "evidence_type": "historical_intraday_chart",
                    "label": "Historical intraday execution context",
                    "source": "Alpaca / MomoPro AI",
                    "observed_at": (
                        reconstruction.get("intraday_context_as_of") or trade.entry_date
                    ),
                    "confidence": confidence or 96,
                    "details": {
                        "intraday_as_of": reconstruction.get("intraday_context_as_of"),
                        "timeframe": reconstruction.get("intraday_timeframe"),
                        "entry_execution_time": reconstruction.get("entry_execution_time"),
                    },
                })

        trade.evidence = evidence
    return trades

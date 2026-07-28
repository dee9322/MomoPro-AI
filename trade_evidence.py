from __future__ import annotations

from trade_classification import classify_trade


def _stop_details(stops):
    ordered = sorted(
        stops,
        key=lambda order: order.submitted_at or order.created_at or order.cancelled_at or order.updated_at or "",
    )
    prices = [float(order.stop_price or order.limit_price or 0) for order in ordered if (order.stop_price or order.limit_price)]
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
            }
            for order in ordered
        ],
        "initial_stop": prices[0] if prices else None,
        "final_stop": prices[-1] if prices else None,
        "stop_changes": len(set(prices)),
    }


def refresh_trade_evidence(trades, orders, executions):
    for trade in trades:
        evidence = []
        if trade.plan_id:
            evidence.append({
                "evidence_type": "official_plan",
                "label": "Official Plan snapshot",
                "source": "MomoPro AI",
                "observed_at": trade.plan_created_at or trade.created_at,
                "confidence": 100,
                "details": {"plan_id": trade.plan_id, "completeness": trade.plan_completeness},
            })

        matched_executions = [execution for execution in executions if execution.matched_trade_id == trade.id]
        if matched_executions:
            evidence.append({
                "evidence_type": "broker_execution",
                "label": f"{len(matched_executions)} broker execution(s)",
                "source": "Webull",
                "observed_at": max(execution.executed_at for execution in matched_executions),
                "confidence": 100,
                "details": {"execution_ids": [execution.execution_id for execution in matched_executions]},
            })

        matched_orders = [order for order in orders if order.matched_trade_id == trade.id]
        stops = [order for order in matched_orders if "Stop" in str(order.purpose or "")]
        if stops:
            details = _stop_details(stops)
            observed_times = [
                order.cancelled_at or order.updated_at or order.submitted_at or order.created_at
                for order in stops
                if (order.cancelled_at or order.updated_at or order.submitted_at or order.created_at)
            ]
            evidence.append({
                "evidence_type": "protective_stop",
                "label": f"{len(stops)} protective-stop order(s)",
                "source": "Webull",
                "observed_at": max(observed_times) if observed_times else "Timestamp unavailable",
                "confidence": max(order.purpose_confidence for order in stops),
                "details": details,
            })

        if trade.reconstruction:
            evidence.append({
                "evidence_type": "historical_chart",
                "label": "Historical chart reconstruction",
                "source": "Alpaca / MomoPro AI",
                "observed_at": trade.reconstruction.get("entry_execution_time") or trade.entry_date,
                "confidence": trade.reconstruction.get("evidence_confidence", 0),
                "details": {
                    "daily_as_of": trade.reconstruction.get("daily_context_as_of"),
                    "intraday_as_of": trade.reconstruction.get("intraday_context_as_of"),
                },
            })

        trade.evidence = evidence
        classify_trade(trade)
    return trades

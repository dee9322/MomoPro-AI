from __future__ import annotations

from datetime import datetime, timezone


def _dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _display_price(value: float) -> str:
    return f"${value:.4f}".rstrip("0").rstrip(".")


def build_trade_timeline(trade, orders, executions):
    events: list[dict] = []
    if trade.plan_id:
        events.append({
            "event_at": trade.plan_created_at or trade.created_at,
            "event_type": "plan",
            "title": "Official Plan Saved",
            "description": f"Plan {trade.plan_id}",
            "source": "MomoPro AI",
            "confidence": 100,
        })

    matched_orders = [order for order in orders if order.matched_trade_id == trade.id]
    for order in matched_orders:
        purpose = str(order.purpose or "Broker Order")
        price = order.stop_price or order.limit_price
        submitted_at = order.submitted_at or order.created_at
        if submitted_at and ("Stop" in purpose or "Profit-Taking" in purpose):
            details = f"{order.side} {order.order_type or 'order'} submitted"
            if order.quantity:
                details += f" for {order.quantity:g} shares"
            if price:
                details += f" at {_display_price(price)}"
            events.append({
                "event_at": submitted_at,
                "event_type": "order_submitted",
                "title": purpose.replace("Confirmed ", "").replace("Likely ", "") + " Submitted",
                "description": details,
                "source": "Webull",
                "confidence": order.purpose_confidence,
            })

        status = str(order.status or "").upper().replace(" ", "_").replace("-", "_")
        if status in {"CANCELLED", "CANCELED"}:
            cancelled_at = order.cancelled_at or order.updated_at
            if cancelled_at:
                details = f"{order.side} {order.order_type or 'order'} canceled"
                if order.quantity:
                    details += f" for {order.quantity:g} shares"
                if price:
                    details += f" at {_display_price(price)}"
                events.append({
                    "event_at": cancelled_at,
                    "event_type": "order_cancelled",
                    "title": purpose + " Canceled",
                    "description": details,
                    "source": "Webull",
                    "confidence": order.purpose_confidence,
                })

    for execution in executions:
        if execution.matched_trade_id == trade.id:
            events.append({
                "event_at": execution.executed_at,
                "event_type": "execution",
                "title": f"{execution.side.title()} Filled",
                "description": f"{execution.quantity:g} shares at {_display_price(execution.price)}",
                "source": "Webull",
                "confidence": 100,
            })

    for update in trade.updates:
        events.append({
            "event_at": update.date,
            "event_type": "management",
            "title": update.update_type,
            "description": update.note,
            "source": "Journal",
            "confidence": 100,
        })

    # Keep entries with unknown timestamps out of the chronology rather than
    # pretending the sync time was the broker event time.
    events = [event for event in events if _dt(event.get("event_at")) is not None]
    events.sort(key=lambda event: _dt(event.get("event_at")) or datetime.max.replace(tzinfo=timezone.utc))
    trade.timeline = events
    return events

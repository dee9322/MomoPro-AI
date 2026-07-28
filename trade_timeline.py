from __future__ import annotations

from datetime import datetime, timedelta, timezone

from broker_order_intelligence import has_reliable_broker_time


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


def _append(events: list[dict], *, event_at: str | None, sort_at: datetime, event_type: str,
            title: str, description: str, source: str, confidence: float,
            time_label: str | None = None) -> None:
    events.append({
        "event_at": event_at or "",
        "time_label": time_label or (event_at or "Time unavailable"),
        "event_type": event_type,
        "title": title,
        "description": description,
        "source": source,
        "confidence": confidence,
        "_sort_at": sort_at,
    })


def build_trade_timeline(trade, orders, executions):
    events: list[dict] = []
    entry_time = _dt(trade.entry_date) or datetime.min.replace(tzinfo=timezone.utc)
    exit_time = _dt(trade.exit_date) or entry_time + timedelta(days=3650)

    if trade.plan_id:
        plan_time = _dt(trade.plan_created_at or trade.created_at) or entry_time - timedelta(seconds=1)
        _append(
            events, event_at=trade.plan_created_at or trade.created_at, sort_at=plan_time,
            event_type="plan", title="Official Plan Saved", description=f"Plan {trade.plan_id}",
            source="MomoPro AI", confidence=100,
        )

    matched_executions = [execution for execution in executions if execution.matched_trade_id == trade.id]
    for execution in matched_executions:
        execution_time = _dt(execution.executed_at)
        if not execution_time:
            continue
        _append(
            events, event_at=execution.executed_at, sort_at=execution_time,
            event_type="execution", title=f"{execution.side.title()} Filled",
            description=f"{execution.quantity:g} shares at {_display_price(execution.price)}",
            source="Webull", confidence=100,
        )

    matched_orders = [order for order in orders if order.matched_trade_id == trade.id]
    for index, order in enumerate(matched_orders):
        purpose = str(order.purpose or "Broker Order")
        if "Stop" not in purpose and "Profit-Taking" not in purpose:
            continue
        price = order.stop_price or order.limit_price
        details = f"{order.side} {order.order_type or 'order'}"
        if order.quantity:
            details += f" for {order.quantity:g} shares"
        if price:
            details += f" at {_display_price(price)}"

        reliable_time = has_reliable_broker_time(order)
        submitted_at = order.submitted_at or order.created_at
        status = str(order.status or "").upper().replace(" ", "_").replace("-", "_")
        cancelled_at = order.cancelled_at or order.updated_at

        if reliable_time and _dt(submitted_at):
            _append(
                events, event_at=submitted_at, sort_at=_dt(submitted_at) or entry_time,
                event_type="order_submitted",
                title=purpose.replace("Confirmed ", "").replace("Likely ", "") + " Submitted",
                description=details + " submitted", source="Webull", confidence=order.purpose_confidence,
            )
            if status in {"CANCELLED", "CANCELED"} and _dt(cancelled_at):
                _append(
                    events, event_at=cancelled_at, sort_at=_dt(cancelled_at) or exit_time,
                    event_type="order_cancelled", title=purpose + " Canceled",
                    description=details + " canceled", source="Webull", confidence=order.purpose_confidence,
                )
        else:
            # Webull did not return trustworthy lifecycle timestamps. Keep the event
            # visible without pretending the later sync timestamp was the actual time.
            inferred_sort = entry_time + timedelta(seconds=10 + index)
            _append(
                events, event_at=None, sort_at=inferred_sort,
                event_type="order_observed", title=purpose + " Observed",
                description=details + "; exact broker submission/cancellation time unavailable",
                source="Webull", confidence=order.purpose_confidence,
                time_label="During trade — exact broker time unavailable",
            )

    for update in trade.updates:
        update_time = _dt(update.date)
        if update_time:
            _append(
                events, event_at=update.date, sort_at=update_time,
                event_type="management", title=update.update_type,
                description=update.note, source="Journal", confidence=100,
            )

    events.sort(key=lambda event: event["_sort_at"])
    for event in events:
        event.pop("_sort_at", None)
    trade.timeline = events
    return events

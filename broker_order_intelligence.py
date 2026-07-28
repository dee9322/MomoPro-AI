from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from broker_models import BrokerOrder
from trade_models import TradeRecord


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


def order_event_time(order: BrokerOrder) -> datetime | None:
    status = str(order.status or "").upper().replace("-", "_").replace(" ", "_")
    if status in {"CANCELED", "CANCELLED"}:
        return _dt(order.cancelled_at) or _dt(order.updated_at) or _dt(order.submitted_at)
    if order.filled_quantity > 0:
        return _dt(order.filled_at) or _dt(order.updated_at) or _dt(order.submitted_at)
    return _dt(order.updated_at) or _dt(order.submitted_at)


def order_fingerprint(order: dict[str, Any]) -> str:
    raw = "|".join(
        str(order.get(key, "") or "")
        for key in (
            "account_id", "order_id", "symbol", "side", "status", "quantity",
            "filled_quantity", "limit_price", "stop_price", "submitted_at",
            "filled_at", "cancelled_at", "updated_at",
        )
    )
    return sha256(raw.encode()).hexdigest()


def to_broker_order(order: dict[str, Any]) -> BrokerOrder:
    return BrokerOrder(
        fingerprint=order_fingerprint(order),
        account_id=str(order.get("account_id") or ""),
        order_id=str(order.get("order_id") or ""),
        client_order_id=str(order.get("client_order_id") or ""),
        broker_order_id=str(order.get("broker_order_id") or ""),
        symbol=str(order.get("symbol") or "").upper(),
        side=str(order.get("side") or "").upper(),
        status=str(order.get("status") or "Unknown"),
        order_type=str(order.get("order_type") or ""),
        quantity=float(order.get("quantity") or 0),
        filled_quantity=float(order.get("filled_quantity") or 0),
        average_price=float(order.get("average_price") or 0),
        limit_price=float(order.get("limit_price") or 0),
        stop_price=float(order.get("stop_price") or 0),
        submitted_at=str(order.get("submitted_at") or order.get("created_at") or ""),
        filled_at=str(order.get("filled_at") or ""),
        cancelled_at=str(order.get("cancelled_at") or ""),
        created_at=str(order.get("created_at") or order.get("submitted_at") or ""),
        updated_at=str(order.get("updated_at") or ""),
        synced_at=str(order.get("synced_at") or ""),
        raw=order.get("raw") if isinstance(order.get("raw"), dict) else {},
    )


def merge_orders(existing: list[BrokerOrder], normalized: list[dict[str, Any]]) -> list[BrokerOrder]:
    by_key = {(order.account_id, order.order_id): order for order in existing}
    protected = {"id", "matched_trade_id", "purpose", "purpose_confidence", "relationship_group"}
    for row in normalized:
        incoming = to_broker_order(row)
        key = (incoming.account_id, incoming.order_id)
        current = by_key.get(key)
        if current is None:
            by_key[key] = incoming
            continue
        for name in incoming.__dataclass_fields__:
            if name in protected:
                continue
            value = getattr(incoming, name)
            if value not in ("", None, 0, 0.0, {}):
                setattr(current, name, value)
        current.status = incoming.status or current.status
        current.synced_at = incoming.synced_at or current.synced_at
        current.fingerprint = order_fingerprint(current.to_dict())
    return list(by_key.values())


def _trade_window_contains(trade: TradeRecord, when: datetime | None) -> bool:
    if when is None:
        return True
    entry = _dt(trade.entry_date)
    exit_at = _dt(trade.exit_date)
    if entry and when < entry - timedelta(days=2):
        return False
    if exit_at and when > exit_at + timedelta(days=2):
        return False
    return True


def link_and_classify_orders(orders: list[BrokerOrder], trades: list[TradeRecord]) -> list[BrokerOrder]:
    for order in orders:
        when = order_event_time(order)
        candidates = [trade for trade in trades if trade.symbol == order.symbol and _trade_window_contains(trade, when)]
        candidates.sort(
            key=lambda trade: abs((when - _dt(trade.entry_date)).total_seconds())
            if when and _dt(trade.entry_date) else 10**18
        )
        trade = candidates[0] if candidates else None
        if trade:
            order.matched_trade_id = trade.id
            order.relationship_group = trade.id
            if order.order_id and order.order_id not in trade.broker_order_ids:
                trade.broker_order_ids.append(order.order_id)

        status = str(order.status or "").upper().replace(" ", "_").replace("-", "_")
        order_type = str(order.order_type or "").upper().replace(" ", "_").replace("-", "_")
        is_stop = order.side == "SELL" and ("STOP" in order_type or order.stop_price > 0)

        if is_stop and trade:
            order.purpose = "Confirmed Protective Stop"
            order.purpose_confidence = 98
        elif is_stop:
            order.purpose = "Likely Protective Stop"
            order.purpose_confidence = 82
        elif (
            order.side == "SELL" and status in {"CANCELLED", "CANCELED"} and trade
            and order.quantity and abs(order.quantity - trade.remaining_shares) <= max(1, trade.shares * 0.05)
        ):
            order.purpose = "Likely Protective Stop"
            order.purpose_confidence = 84
        elif trade and order.side == "SELL" and order.limit_price > trade.entry_price:
            order.purpose = "Profit-Taking Order"
            order.purpose_confidence = 82
        elif status in {"CANCELLED", "CANCELED"}:
            order.purpose = "Canceled Order — Purpose Unknown"
            order.purpose_confidence = 35
        else:
            order.purpose = "Execution / Position Order"
            order.purpose_confidence = 90 if order.filled_quantity else 55
    return orders

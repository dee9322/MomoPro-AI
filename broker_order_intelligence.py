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


def _seconds_apart(a: object, b: object) -> float | None:
    left, right = _dt(a), _dt(b)
    if not left or not right:
        return None
    return abs((left - right).total_seconds())


def has_reliable_broker_time(order: BrokerOrder) -> bool:
    """Return False when Webull only supplied the later synchronization time.

    Historical canceled orders sometimes arrive with submitted/canceled/updated values
    all equal to the sync timestamp. Those values are useful as an observation time,
    but they are not trustworthy broker lifecycle timestamps.
    """
    synced = _dt(order.synced_at)
    submitted = _dt(order.submitted_at or order.created_at)
    cancelled = _dt(order.cancelled_at)
    updated = _dt(order.updated_at)
    filled = _dt(order.filled_at)

    if filled and (not synced or abs((filled - synced).total_seconds()) > 120):
        return True

    event_times = [value for value in (submitted, cancelled, updated) if value]
    if not event_times:
        return False
    if synced and all(abs((value - synced).total_seconds()) <= 120 for value in event_times):
        return False
    if len(event_times) >= 2 and max(event_times) - min(event_times) <= timedelta(seconds=5):
        return False
    return True


def order_event_time(order: BrokerOrder) -> datetime | None:
    if not has_reliable_broker_time(order):
        return None
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


def _quantity_similarity(order: BrokerOrder, trade: TradeRecord) -> float:
    if order.quantity <= 0 or trade.shares <= 0:
        return 0.0
    difference = abs(order.quantity - trade.shares)
    tolerance = max(1.0, trade.shares * 0.03)
    if difference <= tolerance:
        return 1.0
    if difference <= max(2.0, trade.shares * 0.10):
        return 0.65
    return max(0.0, 1.0 - difference / max(order.quantity, trade.shares)) * 0.35


def _candidate_score(order: BrokerOrder, trade: TradeRecord, when: datetime | None) -> float:
    score = _quantity_similarity(order, trade) * 60
    if order.side == "SELL" and (order.stop_price or 0) > 0:
        if trade.direction.lower() == "long" and order.stop_price < trade.entry_price:
            score += 18
        elif trade.direction.lower() != "long" and order.stop_price > trade.entry_price:
            score += 18
    if order.side == "SELL" and order.limit_price and order.limit_price > trade.entry_price:
        score += 10
    if when and _trade_window_contains(trade, when):
        score += 25
        entry = _dt(trade.entry_date)
        if entry:
            distance_days = abs((when - entry).total_seconds()) / 86400
            score += max(0, 12 - min(distance_days, 12))
    if order.order_id and order.order_id in trade.broker_order_ids:
        score += 25
    return score


def _select_trade(order: BrokerOrder, trades: list[TradeRecord]) -> tuple[TradeRecord | None, bool]:
    when = order_event_time(order)
    candidates = [trade for trade in trades if trade.symbol == order.symbol]
    if when:
        candidates = [trade for trade in candidates if _trade_window_contains(trade, when)]
    if not candidates:
        return None, False

    ranked = sorted(
        ((_candidate_score(order, trade, when), trade) for trade in candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best_trade = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else -1
    reliable_time = when is not None
    minimum = 35 if reliable_time else 50
    if best_score < minimum or (second_score >= 0 and best_score - second_score < 8):
        return None, reliable_time
    return best_trade, reliable_time


def link_and_classify_orders(orders: list[BrokerOrder], trades: list[TradeRecord]) -> list[BrokerOrder]:
    for order in orders:
        trade, matched_by_reliable_time = _select_trade(order, trades)
        if trade:
            order.matched_trade_id = trade.id
            order.relationship_group = trade.id
            if order.order_id and order.order_id not in trade.broker_order_ids:
                trade.broker_order_ids.append(order.order_id)

        status = str(order.status or "").upper().replace(" ", "_").replace("-", "_")
        order_type = str(order.order_type or "").upper().replace(" ", "_").replace("-", "_")
        is_stop = order.side == "SELL" and ("STOP" in order_type or order.stop_price > 0)

        if is_stop and trade:
            exact_quantity = _quantity_similarity(order, trade) >= 0.99
            order.purpose = "Confirmed Protective Stop"
            order.purpose_confidence = 98 if matched_by_reliable_time else 94 if exact_quantity else 88
        elif is_stop:
            order.purpose = "Likely Protective Stop"
            order.purpose_confidence = 82
        elif (
            order.side == "SELL" and status in {"CANCELLED", "CANCELED"} and trade
            and order.quantity and abs(order.quantity - trade.shares) <= max(1, trade.shares * 0.05)
        ):
            order.purpose = "Likely Protective Stop"
            order.purpose_confidence = 84 if matched_by_reliable_time else 78
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

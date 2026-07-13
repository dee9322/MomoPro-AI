from __future__ import annotations

from datetime import datetime
from typing import Any

from broker_models import BrokerExecution
from trade_models import TradeRecord, TradeExit, utc_now


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _active_trade_at(trades: list[TradeRecord], symbol: str, executed_at: str) -> TradeRecord | None:
    execution_time = _parse_time(executed_at)
    candidates: list[TradeRecord] = []
    for trade in trades:
        if trade.symbol != symbol or trade.status not in {"open", "partial"}:
            continue
        entry_time = _parse_time(trade.entry_date)
        if execution_time is not None and entry_time is not None and entry_time > execution_time:
            continue
        candidates.append(trade)
    candidates.sort(key=lambda trade: trade.entry_date)
    return candidates[0] if candidates else None


def _manual_trade_match(trades: list[TradeRecord], execution: BrokerExecution) -> TradeRecord | None:
    """Match a broker buy to a nearby manual plan without attaching old history to a future trade."""
    execution_time = _parse_time(execution.executed_at)
    matches: list[tuple[float, TradeRecord]] = []
    for trade in trades:
        if trade.symbol != execution.symbol or trade.status not in {"open", "partial"}:
            continue
        if trade.broker_execution_ids:
            continue
        entry_time = _parse_time(trade.entry_date)
        if execution_time is None or entry_time is None:
            continue
        day_gap = abs((entry_time.date() - execution_time.date()).days)
        if day_gap > 7:
            continue
        price_gap = abs(float(trade.entry_price or 0) - execution.price) / max(execution.price, 0.000001)
        matches.append((day_gap + price_gap, trade))
    matches.sort(key=lambda pair: pair[0])
    return matches[0][1] if matches else None


def _weighted_average(old_price: float, old_qty: float, new_price: float, new_qty: float) -> float:
    total = old_qty + new_qty
    return round(((old_price * old_qty) + (new_price * new_qty)) / total, 6) if total > 0 else new_price


def reconcile_executions(
    trades: list[TradeRecord],
    executions: list[BrokerExecution],
) -> tuple[list[TradeRecord], list[BrokerExecution], dict[str, Any]]:
    """Apply unlinked executions to journal trades using chronological FIFO logic."""
    summary = {
        "new_trades": 0,
        "updated_trades": 0,
        "partial_exits": 0,
        "closed_trades": 0,
        "unmatched_executions": 0,
    }
    touched_existing: set[str] = set()
    newly_created: set[str] = set()
    all_applied = {execution_id for trade in trades for execution_id in trade.broker_execution_ids}
    pending = [execution for execution in executions if execution.id not in all_applied and not execution.matched_trade_id]
    pending.sort(key=lambda execution: execution.executed_at)

    for execution in pending:
        symbol = execution.symbol.upper()
        if execution.side == "BUY":
            trade = _manual_trade_match(trades, execution) or _active_trade_at(trades, symbol, execution.executed_at)
            if trade is None:
                trade = TradeRecord(
                    symbol=symbol,
                    status="open",
                    direction="long",
                    entry_date=execution.executed_at,
                    entry_price=execution.price,
                    shares=execution.quantity,
                    source="broker_import",
                    broker="Webull",
                    broker_execution_ids=[execution.id],
                    broker_fees=execution.fees,
                    notes="Created automatically from Webull execution history.",
                )
                trades.append(trade)
                newly_created.add(trade.id)
                summary["new_trades"] += 1
            else:
                remaining_before = trade.remaining_shares
                # A nearby manual plan may already contain the intended shares. Replace the plan quantity
                # on its first broker match; subsequent buys accumulate normally.
                if not trade.broker_execution_ids and trade.source == "manual":
                    trade.entry_price = execution.price
                    trade.shares = execution.quantity
                    trade.source = "journal+broker"
                else:
                    trade.entry_price = _weighted_average(trade.entry_price, remaining_before, execution.price, execution.quantity)
                    trade.shares = round(trade.shares + execution.quantity, 8)
                trade.broker_execution_ids.append(execution.id)
                trade.broker_fees = round(float(trade.broker_fees or 0) + execution.fees, 6)
                trade.broker = "Webull"
                trade.updated_at = utc_now()
                touched_existing.add(trade.id)
            execution.matched_trade_id = trade.id
            continue

        remaining_to_apply = execution.quantity
        matched_any = False
        while remaining_to_apply > 1e-8:
            trade = _active_trade_at(trades, symbol, execution.executed_at)
            if trade is None or trade.remaining_shares <= 0:
                break
            allocated = min(remaining_to_apply, trade.remaining_shares)
            trade.exits.append(
                TradeExit(
                    date=execution.executed_at,
                    shares=allocated,
                    price=execution.price,
                    reason="Webull Imported Exit",
                    notes=f"Imported from {execution.source_file}. Order ID: {execution.order_id or 'Unavailable'}",
                )
            )
            trade.broker_execution_ids.append(execution.id)
            trade.broker_fees = round(float(trade.broker_fees or 0) + execution.fees, 6)
            trade.source = "broker_import" if trade.source == "broker_import" else "journal+broker"
            trade.broker = "Webull"
            trade.updated_at = utc_now()
            if trade.remaining_shares <= 1e-8:
                trade.status = "closed"
                trade.exit_date = execution.executed_at
                trade.exit_reason = "Webull Imported Exit"
                summary["closed_trades"] += 1
            else:
                trade.status = "partial"
                summary["partial_exits"] += 1
            touched_existing.add(trade.id)
            execution.matched_trade_id = trade.id
            matched_any = True
            remaining_to_apply = round(remaining_to_apply - allocated, 8)
        if not matched_any or remaining_to_apply > 1e-8:
            summary["unmatched_executions"] += 1

    summary["updated_trades"] = len(touched_existing - newly_created)
    return trades, executions, summary


def unmatched_executions(executions: list[BrokerExecution]) -> list[BrokerExecution]:
    return [execution for execution in executions if not execution.matched_trade_id]

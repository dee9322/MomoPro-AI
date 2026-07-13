from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from trade_models import TradeExit, TradeRecord, TradeUpdate, utc_now
from broker_import import build_import
from broker_reconciliation import reconcile_executions, unmatched_executions
from trade_storage import (
    load_broker_executions, load_broker_imports, load_trades, save_broker_state, save_trades,
)


def normalize_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    if not value or len(value) > 12 or any(not (char.isalnum() or char in ".-") for char in value):
        raise ValueError("Enter a valid ticker symbol.")
    return value


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def create_trade(**values: Any) -> TradeRecord:
    symbol = normalize_symbol(values.get("symbol", ""))
    entry_price = float(values.get("entry_price") or 0)
    shares = float(values.get("shares") or 0)
    stop = _number(values.get("initial_stop"))
    if entry_price <= 0:
        raise ValueError("Entry price must be greater than zero.")
    if shares <= 0:
        raise ValueError("Shares must be greater than zero.")
    if stop is not None and stop >= entry_price and str(values.get("direction", "long")).lower() == "long":
        raise ValueError("For a long trade, the initial stop must be below the entry price.")

    trades = load_trades()
    duplicate = any(
        trade.symbol == symbol and trade.status in {"open", "partial"} and abs(trade.entry_price - entry_price) < 0.000001
        for trade in trades
    )
    if duplicate:
        raise ValueError("An open trade with this ticker and entry price already exists.")

    allowed = {name for name in TradeRecord.__dataclass_fields__}
    payload = {key: value for key, value in values.items() if key in allowed}
    payload.update(symbol=symbol, entry_price=entry_price, shares=shares, initial_stop=stop, current_stop=stop)
    trade = TradeRecord(**payload)
    trade.status = "open"
    trades.append(trade)
    save_trades(trades)
    return trade


def get_trade(trade_id: str) -> TradeRecord | None:
    return next((trade for trade in load_trades() if trade.id == trade_id), None)


def update_trade(trade_id: str, **changes: Any) -> TradeRecord:
    trades = load_trades()
    for index, trade in enumerate(trades):
        if trade.id != trade_id:
            continue
        for key, value in changes.items():
            if key == "symbol":
                value = normalize_symbol(value)
            if hasattr(trade, key) and key not in {"id", "created_at"}:
                setattr(trade, key, value)
        trade.updated_at = utc_now()
        trades[index] = trade
        save_trades(trades)
        return trade
    raise KeyError("Trade not found.")


def delete_trade(trade_id: str) -> bool:
    trades = load_trades()
    remaining = [trade for trade in trades if trade.id != trade_id]
    if len(remaining) == len(trades):
        return False
    save_trades(remaining)
    return True


def add_management_update(trade_id: str, update_type: str, note: str, stop: float | None = None, current_price: float | None = None) -> TradeRecord:
    trade = get_trade(trade_id)
    if not trade:
        raise KeyError("Trade not found.")
    trade.updates.insert(0, TradeUpdate(update_type=update_type, note=note.strip(), stop=_number(stop), current_price=_number(current_price)))
    if _number(stop) is not None:
        trade.current_stop = _number(stop)
    trade.updated_at = utc_now()
    return update_trade(trade.id, updates=trade.updates, current_stop=trade.current_stop)


def add_exit(trade_id: str, shares: float, price: float, reason: str, notes: str = "", date: str | None = None) -> TradeRecord:
    trade = get_trade(trade_id)
    if not trade:
        raise KeyError("Trade not found.")
    shares = float(shares or 0)
    price = float(price or 0)
    if shares <= 0 or price <= 0:
        raise ValueError("Exit shares and price must be greater than zero.")
    if shares > trade.remaining_shares + 1e-8:
        raise ValueError("Exit shares cannot exceed remaining shares.")
    trade.exits.append(TradeExit(date=date or utc_now(), shares=shares, price=price, reason=reason, notes=notes))
    trade.updated_at = utc_now()
    if trade.remaining_shares <= 1e-8:
        trade.status = "closed"
        trade.exit_date = date or utc_now()
        trade.exit_reason = reason
    else:
        trade.status = "partial"
    trades = load_trades()
    for index, existing in enumerate(trades):
        if existing.id == trade.id:
            trades[index] = trade
            break
    save_trades(trades)
    return trade


def reopen_trade(trade_id: str) -> TradeRecord:
    return update_trade(trade_id, status="open", exit_date=None, exit_reason="")


def realized_pnl(trade: TradeRecord) -> float:
    multiplier = 1 if trade.direction.lower() == "long" else -1
    return round(sum((exit.price - trade.entry_price) * exit.shares * multiplier for exit in trade.exits), 2)


def unrealized_pnl(trade: TradeRecord, current_price: float | None) -> float | None:
    if current_price is None or trade.remaining_shares <= 0:
        return None
    multiplier = 1 if trade.direction.lower() == "long" else -1
    return round((float(current_price) - trade.entry_price) * trade.remaining_shares * multiplier, 2)


def initial_risk_per_share(trade: TradeRecord) -> float | None:
    if trade.initial_stop is None:
        return None
    risk = abs(trade.entry_price - float(trade.initial_stop))
    return risk if risk > 0 else None


def realized_r(trade: TradeRecord) -> float | None:
    risk = initial_risk_per_share(trade)
    if not risk or trade.shares <= 0:
        return None
    return round(realized_pnl(trade) / (risk * trade.shares), 2)


def average_exit_price(trade: TradeRecord) -> float | None:
    shares = trade.exited_shares
    if shares <= 0:
        return None
    return round(sum(exit.price * exit.shares for exit in trade.exits) / shares, 4)


def days_held(trade: TradeRecord) -> int | None:
    try:
        start = datetime.fromisoformat(str(trade.entry_date).replace("Z", "+00:00"))
        end_raw = trade.exit_date if trade.status == "closed" and trade.exit_date else datetime.now(timezone.utc).isoformat()
        end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
        return max((end.date() - start.date()).days, 0)
    except (TypeError, ValueError):
        return None


def trade_summary(trade: TradeRecord, current_price: float | None = None) -> dict[str, Any]:
    return {
        "Symbol": trade.symbol,
        "Status": trade.status.title(),
        "Entry": trade.entry_price,
        "Shares": trade.shares,
        "Remaining": trade.remaining_shares,
        "Current": current_price,
        "Realized P/L": realized_pnl(trade),
        "Unrealized P/L": unrealized_pnl(trade, current_price),
        "Realized R": realized_r(trade),
        "Stop": trade.current_stop,
        "T1": trade.t1,
        "Setup": trade.setup or "—",
        "Grade": trade.grade or "—",
        "AI Confidence": trade.ai_confidence,
        "Momo Score": trade.momo_score,
        "Days Held": days_held(trade),
    }


def import_webull_history(data: bytes, filename: str) -> dict[str, Any]:
    trades = load_trades()
    executions = load_broker_executions()
    imports = load_broker_imports()
    fingerprints = {item.fingerprint for item in executions if item.fingerprint}
    import_record, new_executions = build_import(data, filename, fingerprints)
    executions.extend(new_executions)
    trades, executions, reconciliation = reconcile_executions(trades, executions)
    imports.insert(0, import_record)
    save_broker_state(trades, executions, imports)
    return {
        "import": import_record.to_dict(),
        "reconciliation": reconciliation,
        "unmatched": [item.to_dict() for item in unmatched_executions(executions)],
    }


def broker_import_status() -> dict[str, Any]:
    executions = load_broker_executions()
    imports = load_broker_imports()
    unmatched = unmatched_executions(executions)
    return {
        "connected": bool(imports),
        "broker": "Webull",
        "executions": len(executions),
        "imports": len(imports),
        "last_import": imports[0].imported_at if imports else None,
        "last_file": imports[0].source_file if imports else None,
        "unmatched": len(unmatched),
        "duplicates_skipped": sum(item.duplicates_skipped for item in imports),
    }

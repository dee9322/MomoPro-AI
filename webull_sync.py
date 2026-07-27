from __future__ import annotations

"""Complete read-only Webull synchronization and reconciliation service."""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from broker_models import BrokerExecution, stable_execution_id
from broker_reconciliation import reconcile_executions, unmatched_executions
from integration_models import IntegrationConnection
from integration_storage import get_connection, record_event, save_connection
from trade_storage import (
    load_broker_executions,
    load_broker_imports,
    load_trades,
    save_broker_state,
)
from webull_api import WebullCredentials, WebullReadOnlyClient


SNAPSHOT_PATH = Path(__file__).with_name("webull_sync_data.json")
FILLED_WORDS = {"FILLED", "PARTIALLY_FILLED", "PARTIAL_FILLED", "EXECUTED", "COMPLETED", "COMPLETE"}
BUY_WORDS = {"BUY", "BUY_TO_COVER", "BUYTOCOVER"}
SELL_WORDS = {"SELL", "SELL_SHORT", "SELLSHORT", "SHORT"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.stem + "_", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_webull_snapshot() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        return {
            "schema_version": "0.95-WEBULL-1",
            "last_sync": None,
            "accounts": [],
            "balances": {},
            "positions": [],
            "orders": [],
            "sync_summary": {},
        }
    try:
        value = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _first(data: dict[str, Any], names: Iterable[str], default: Any = None) -> Any:
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        if name in data and data[name] not in (None, ""):
            return data[name]
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return default


def _time(value: Any) -> str:
    if value in (None, ""):
        return utc_now()
    text = str(value).strip()
    if text.isdigit():
        raw = int(text)
        if raw > 10_000_000_000:
            raw /= 1000
        return datetime.fromtimestamp(raw, timezone.utc).isoformat(timespec="seconds")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    except ValueError:
        return text


def _account_id(account: dict[str, Any]) -> str:
    return str(_first(account, ("account_id", "accountId", "id"), "")).strip()


def _symbol(data: dict[str, Any]) -> str:
    symbol = _first(data, ("symbol", "ticker", "instrument_symbol", "instrumentSymbol"), "")
    if not symbol and isinstance(data.get("instrument"), dict):
        symbol = _first(data["instrument"], ("symbol", "ticker"), "")
    return str(symbol or "").strip().upper()


def normalize_account(account: dict[str, Any]) -> dict[str, Any]:
    account_id = _account_id(account)
    return {
        "account_id": account_id,
        "masked_account": ("••••" + account_id[-4:]) if account_id else "—",
        "account_type": str(_first(account, ("account_type", "accountType", "type"), "Unknown")),
        "status": str(_first(account, ("status", "account_status", "accountStatus"), "Active")),
        "currency": str(_first(account, ("currency", "base_currency", "baseCurrency"), "USD")),
        "raw": account,
    }


def normalize_balance(account_id: str, balance: dict[str, Any]) -> dict[str, Any]:
    return {
        "account_id": account_id,
        "net_liquidation": _number(_first(balance, ("net_liquidation", "netLiquidation", "net_account_value", "netAccountValue", "total_assets", "totalAssets"))),
        "cash_balance": _number(_first(balance, ("cash_balance", "cashBalance", "cash", "settled_cash", "settledCash"))),
        "buying_power": _number(_first(balance, ("buying_power", "buyingPower", "day_buying_power", "dayBuyingPower"))),
        "market_value": _number(_first(balance, ("market_value", "marketValue", "positions_market_value", "positionsMarketValue"))),
        "unrealized_pnl": _number(_first(balance, ("unrealized_pnl", "unrealizedPnl", "unrealized_profit_loss", "unrealizedProfitLoss"))),
        "realized_pnl": _number(_first(balance, ("realized_pnl", "realizedPnl", "realized_profit_loss", "realizedProfitLoss"))),
        "currency": str(_first(balance, ("currency", "base_currency", "baseCurrency"), "USD")),
        "raw": balance,
    }


def normalize_position(account_id: str, position: dict[str, Any]) -> dict[str, Any]:
    quantity = _number(_first(position, ("quantity", "qty", "position", "total_quantity", "totalQuantity")))
    average_cost = _number(_first(position, ("average_cost", "averageCost", "avg_cost", "avgCost", "cost_price", "costPrice")))
    last_price = _number(_first(position, ("last_price", "lastPrice", "market_price", "marketPrice", "current_price", "currentPrice")))
    market_value = _number(_first(position, ("market_value", "marketValue")), quantity * last_price)
    unrealized = _number(_first(position, ("unrealized_pnl", "unrealizedPnl", "unrealized_profit_loss", "unrealizedProfitLoss")), market_value - quantity * average_cost)
    return {
        "account_id": account_id,
        "symbol": _symbol(position),
        "quantity": quantity,
        "average_cost": average_cost,
        "last_price": last_price,
        "market_value": market_value,
        "unrealized_pnl": unrealized,
        "unrealized_pnl_pct": _number(_first(position, ("unrealized_pnl_ratio", "unrealizedPnlRatio", "unrealized_return", "unrealizedReturn"))),
        "side": str(_first(position, ("side", "position_side", "positionSide"), "LONG")),
        "currency": str(_first(position, ("currency",), "USD")),
        "raw": position,
    }


def normalize_order(account_id: str, order: dict[str, Any]) -> dict[str, Any]:
    order_id = str(_first(order, ("order_id", "orderId", "client_order_id", "clientOrderId", "id"), ""))
    status = str(_first(order, ("status", "order_status", "orderStatus"), "Unknown"))
    side = str(_first(order, ("side", "action"), "")).upper()
    return {
        "account_id": account_id,
        "order_id": order_id,
        "symbol": _symbol(order),
        "side": side,
        "status": status,
        "order_type": str(_first(order, ("order_type", "orderType", "type"), "")),
        "quantity": _number(_first(order, ("quantity", "qty", "total_quantity", "totalQuantity"))),
        "filled_quantity": _number(_first(order, ("filled_quantity", "filledQuantity", "filled_qty", "filledQty", "executed_quantity", "executedQuantity"))),
        "average_price": _number(_first(order, ("average_price", "averagePrice", "avg_price", "avgPrice", "filled_price", "filledPrice"))),
        "limit_price": _number(_first(order, ("limit_price", "limitPrice"))),
        "created_at": _time(_first(order, ("created_at", "createdAt", "create_time", "createTime", "placed_time", "placedTime"))),
        "updated_at": _time(_first(order, ("updated_at", "updatedAt", "update_time", "updateTime", "filled_time", "filledTime"))),
        "raw": order,
    }


def _nested_execution_rows(order: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("executions", "fills", "filled_details", "filledDetails", "trades", "transactions"):
        value = order.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            rows.append(value)
    return rows


def order_to_executions(order: dict[str, Any]) -> list[BrokerExecution]:
    raw_order = order.get("raw") if isinstance(order.get("raw"), dict) else order
    account_id = str(order.get("account_id") or "")
    order_id = str(order.get("order_id") or "")
    symbol = str(order.get("symbol") or "").upper()
    side = str(order.get("side") or "").upper()
    status = str(order.get("status") or "").upper().replace(" ", "_")
    if side in BUY_WORDS:
        normalized_side = "BUY"
    elif side in SELL_WORDS:
        normalized_side = "SELL"
    else:
        return []

    fills = _nested_execution_rows(raw_order)
    if not fills and (status in FILLED_WORDS or float(order.get("filled_quantity") or 0) > 0):
        fills = [raw_order]

    results: list[BrokerExecution] = []
    for index, fill in enumerate(fills):
        quantity = _number(_first(fill, ("quantity", "qty", "filled_quantity", "filledQuantity", "executed_quantity", "executedQuantity")), float(order.get("filled_quantity") or 0))
        price = _number(_first(fill, ("price", "filled_price", "filledPrice", "execution_price", "executionPrice", "average_price", "averagePrice")), float(order.get("average_price") or 0))
        if quantity <= 0 or price <= 0 or not symbol:
            continue
        executed_at = _time(_first(fill, ("executed_at", "executedAt", "filled_time", "filledTime", "trade_time", "tradeTime", "time", "timestamp"), order.get("updated_at")))
        execution_id = str(_first(fill, ("execution_id", "executionId", "trade_id", "tradeId", "fill_id", "fillId", "id"), f"{order_id}-{index}"))
        fees = _number(_first(fill, ("fees", "fee", "commission", "commissions")))
        fingerprint = stable_execution_id(
            "Webull", account_id, execution_id, order_id, symbol,
            normalized_side, quantity, price, executed_at,
        )
        results.append(BrokerExecution(
            fingerprint=fingerprint,
            broker="Webull",
            account_id=account_id,
            order_id=order_id,
            execution_id=execution_id,
            symbol=symbol,
            side=normalized_side,
            quantity=quantity,
            price=price,
            executed_at=executed_at,
            fees=fees,
            currency=str(_first(fill, ("currency",), "USD")),
            status="Filled",
            source_file="Webull OpenAPI",
            import_id="webull_openapi",
            raw={"order": raw_order, "fill": fill},
        ))
    return results


@dataclass
class WebullSyncResult:
    ok: bool
    started_at: str
    completed_at: str | None = None
    accounts: int = 0
    positions: int = 0
    orders: int = 0
    new_executions: int = 0
    duplicates_skipped: int = 0
    reconciliation: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sync_webull(
    app_key: str,
    app_secret: str,
    environment: str = "production",
    history_days: int = 730,
) -> dict[str, Any]:
    started = utc_now()
    result = WebullSyncResult(ok=False, started_at=started)
    try:
        client = WebullReadOnlyClient(WebullCredentials(
            app_key=app_key,
            app_secret=app_secret,
            environment=environment,
        ))
        raw_accounts = client.get_accounts()
        accounts = [normalize_account(item) for item in raw_accounts]
        accounts = [item for item in accounts if item["account_id"]]
        if not accounts:
            raise RuntimeError("Webull connected, but no brokerage accounts were returned.")

        balances: dict[str, Any] = {}
        positions: list[dict[str, Any]] = []
        orders: list[dict[str, Any]] = []
        errors: list[str] = []
        start_dt = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=max(1, int(history_days)))

        for account in accounts:
            account_id = account["account_id"]
            try:
                balances[account_id] = normalize_balance(account_id, client.get_balance(account_id))
            except Exception as error:
                errors.append(f"Balance {account['masked_account']}: {error}")
            try:
                positions.extend(normalize_position(account_id, item) for item in client.get_positions(account_id))
            except Exception as error:
                errors.append(f"Positions {account['masked_account']}: {error}")
            try:
                account_orders = client.get_orders(account_id, start_time=start_dt)
                normalized_orders = [normalize_order(account_id, item) for item in account_orders]
                # Fetch detail only when list data lacks fills and an order ID is available.
                for item in normalized_orders:
                    if item["filled_quantity"] <= 0 and item["order_id"]:
                        try:
                            detail = client.get_order_detail(account_id, item["order_id"])
                            if detail:
                                item = normalize_order(account_id, {**item["raw"], **detail})
                        except Exception:
                            pass
                    orders.append(item)
            except Exception as error:
                errors.append(f"Orders {account['masked_account']}: {error}")

        existing = load_broker_executions()
        fingerprints = {item.fingerprint for item in existing if item.fingerprint}
        new_executions: list[BrokerExecution] = []
        duplicates = 0
        for order in orders:
            for execution in order_to_executions(order):
                if execution.fingerprint in fingerprints:
                    duplicates += 1
                    continue
                fingerprints.add(execution.fingerprint)
                new_executions.append(execution)

        all_executions = existing + new_executions
        trades = load_trades()
        imports = load_broker_imports()
        trades, all_executions, reconciliation = reconcile_executions(trades, all_executions)
        save_broker_state(trades, all_executions, imports)

        completed = utc_now()
        result.ok = True
        result.completed_at = completed
        result.accounts = len(accounts)
        result.positions = len([item for item in positions if item.get("symbol")])
        result.orders = len(orders)
        result.new_executions = len(new_executions)
        result.duplicates_skipped = duplicates
        result.reconciliation = reconciliation
        result.errors = errors

        snapshot = {
            "schema_version": "0.95-WEBULL-1",
            "mode": "read_only",
            "environment": environment,
            "last_sync": completed,
            "accounts": accounts,
            "balances": balances,
            "positions": positions,
            "orders": orders,
            "sync_summary": result.to_dict(),
            "unmatched_executions": len(unmatched_executions(all_executions)),
        }
        _atomic_json_write(SNAPSHOT_PATH, snapshot)
        save_connection(IntegrationConnection(
            integration="webull",
            status="connected" if not errors else "connected_with_warnings",
            mode="read_only",
            last_sync=completed,
            message="Webull read-only synchronization completed." if not errors else "Sync completed with warnings.",
            metadata={
                "environment": environment,
                "accounts": len(accounts),
                "positions": result.positions,
                "orders": result.orders,
                "new_executions": result.new_executions,
                "warnings": errors,
            },
        ))
        record_event({
            "source": "webull",
            "type": "sync_completed",
            "timestamp": completed,
            "summary": result.to_dict(),
        })
        return {"result": result.to_dict(), "snapshot": snapshot}
    except Exception as error:
        completed = utc_now()
        result.completed_at = completed
        result.errors.append(str(error))
        save_connection(IntegrationConnection(
            integration="webull",
            status="error",
            mode="read_only",
            last_sync=None,
            message=str(error),
            metadata={"environment": environment},
        ))
        record_event({
            "source": "webull",
            "type": "sync_failed",
            "timestamp": completed,
            "error": str(error),
        })
        return {"result": result.to_dict(), "snapshot": load_webull_snapshot()}


def webull_connection_status() -> dict[str, Any]:
    connection = get_connection("webull") or {}
    snapshot = load_webull_snapshot()
    return {
        "status": connection.get("status", "not_connected"),
        "mode": connection.get("mode", "read_only"),
        "last_sync": connection.get("last_sync") or snapshot.get("last_sync"),
        "message": connection.get("message", ""),
        "metadata": connection.get("metadata", {}),
        "accounts": len(snapshot.get("accounts") or []),
        "positions": len(snapshot.get("positions") or []),
        "orders": len(snapshot.get("orders") or []),
        "snapshot": snapshot,
    }

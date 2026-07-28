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
    load_broker_executions, load_broker_orders,
    load_broker_imports,
    load_trades,
    save_broker_state,
)
from broker_order_intelligence import merge_orders, link_and_classify_orders
from trade_evidence import refresh_trade_evidence
from trade_classification import classify_trade
from trade_timeline import build_trade_timeline
from webull_api import WebullCredentials, WebullReadOnlyClient, safe_shape


SNAPSHOT_PATH = Path(__file__).with_name("webull_sync_data.json")
DETAIL_CACHE_PATH = Path(__file__).with_name("webull_order_detail_cache.json")
MAX_DETAIL_CALLS_PER_SYNC = 24
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



def _load_detail_cache() -> dict[str, Any]:
    if not DETAIL_CACHE_PATH.exists():
        return {}
    try:
        value = json.loads(DETAIL_CACHE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_detail_cache(cache: dict[str, Any]) -> None:
    _atomic_json_write(DETAIL_CACHE_PATH, cache)


def load_webull_snapshot() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        return {
            "schema_version": "0.95-WEBULL-3",
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


def _deep_values(data: Any, names: Iterable[str]) -> list[Any]:
    wanted = {name.lower().replace("_", "") for name in names}
    found: list[Any] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).lower().replace("_", "") in wanted and value not in (None, ""):
                found.append(value)
            found.extend(_deep_values(value, names))
    elif isinstance(data, list):
        for item in data:
            found.extend(_deep_values(item, names))
    return found


def _deep_first(data: Any, names: Iterable[str], default: Any = None) -> Any:
    values = _deep_values(data, names)
    return values[0] if values else default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return default


def _time(value: Any) -> str:
    if value in (None, ""):
        return ""
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
    symbol = _deep_first(
        data,
        ("symbol", "ticker", "instrument_symbol", "instrumentSymbol", "security_symbol", "securitySymbol"),
        "",
    )
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
    # Webull may nest monetary values under currency/account/category objects.
    # Search the complete payload rather than assuming one flat response shape.
    return {
        "account_id": account_id,
        "net_liquidation": _number(_deep_first(balance, ("net_liquidation", "netLiquidation", "net_account_value", "netAccountValue", "total_assets", "totalAssets", "total_asset", "totalAsset", "net_value", "netValue"))),
        "cash_balance": _number(_deep_first(balance, ("cash_balance", "cashBalance", "cash", "settled_cash", "settledCash", "cash_available_for_withdrawal", "cashAvailableForWithdrawal", "cash_value", "cashValue"))),
        "buying_power": _number(_deep_first(balance, ("buying_power", "buyingPower", "day_buying_power", "dayBuyingPower", "overnight_buying_power", "overnightBuyingPower", "cash_available_for_trade", "cashAvailableForTrade"))),
        "market_value": _number(_deep_first(balance, ("market_value", "marketValue", "positions_market_value", "positionsMarketValue", "position_market_value", "positionMarketValue", "stock_market_value", "stockMarketValue"))),
        "unrealized_pnl": _number(_deep_first(balance, ("unrealized_pnl", "unrealizedPnl", "unrealized_profit_loss", "unrealizedProfitLoss", "unrealized_profit", "unrealizedProfit"))),
        "realized_pnl": _number(_deep_first(balance, ("realized_pnl", "realizedPnl", "realized_profit_loss", "realizedProfitLoss", "realized_profit", "realizedProfit"))),
        "currency": str(_deep_first(balance, ("currency", "base_currency", "baseCurrency"), "USD")),
        "raw": balance,
    }


def normalize_position(account_id: str, position: dict[str, Any]) -> dict[str, Any]:
    quantity = _number(_deep_first(position, ("quantity", "qty", "position", "total_quantity", "totalQuantity", "position_qty", "positionQty")))
    average_cost = _number(_deep_first(position, ("average_cost", "averageCost", "avg_cost", "avgCost", "cost_price", "costPrice", "cost_basis", "costBasis")))
    last_price = _number(_deep_first(position, ("last_price", "lastPrice", "market_price", "marketPrice", "current_price", "currentPrice", "mark_price", "markPrice")))
    market_value = _number(_deep_first(position, ("market_value", "marketValue", "position_market_value", "positionMarketValue")), quantity * last_price)
    unrealized = _number(_deep_first(position, ("unrealized_pnl", "unrealizedPnl", "unrealized_profit_loss", "unrealizedProfitLoss", "unrealized_profit", "unrealizedProfit")), market_value - quantity * average_cost)
    return {
        "account_id": account_id,
        "symbol": _symbol(position),
        "quantity": quantity,
        "average_cost": average_cost,
        "last_price": last_price,
        "market_value": market_value,
        "unrealized_pnl": unrealized,
        "unrealized_pnl_pct": _number(_deep_first(position, ("unrealized_pnl_ratio", "unrealizedPnlRatio", "unrealized_return", "unrealizedReturn", "unrealized_profit_rate", "unrealizedProfitRate"))),
        "side": str(_deep_first(position, ("side", "position_side", "positionSide"), "LONG")),
        "currency": str(_deep_first(position, ("currency",), "USD")),
        "raw": position,
    }


def normalize_order(account_id: str, order: dict[str, Any]) -> dict[str, Any]:
    client_order_id = str(_deep_first(order, ("client_order_id", "clientOrderId"), ""))
    broker_order_id = str(_deep_first(order, ("order_id", "orderId"), ""))
    order_id = client_order_id or broker_order_id
    status = str(_deep_first(order, ("status", "order_status", "orderStatus"), "Unknown"))
    normalized_status = status.upper().replace(" ", "_").replace("-", "_")
    side = str(_deep_first(order, ("side", "action"), "")).upper()
    order_type = str(_deep_first(order, ("order_type", "orderType", "type"), ""))
    normalized_type = order_type.upper().replace(" ", "_").replace("-", "_")
    quantity = _number(_deep_first(order, ("quantity", "qty", "total_quantity", "totalQuantity", "order_quantity", "orderQuantity")))
    filled_quantity = _number(_deep_first(order, ("filled_quantity", "filledQuantity", "filled_qty", "filledQty", "executed_quantity", "executedQuantity", "cumulative_quantity", "cumulativeQuantity")))

    average_price = _number(_deep_first(order, ("average_price", "averagePrice", "avg_price", "avgPrice", "filled_price", "filledPrice", "average_filled_price", "averageFilledPrice", "execution_price", "executionPrice")))
    limit_price = _number(_deep_first(order, ("limit_price", "limitPrice")))
    raw_stop_price = _number(_deep_first(order, ("stop_price", "stopPrice", "aux_price", "auxPrice", "trigger_price", "triggerPrice")))

    fills = _nested_execution_rows(order)
    if average_price <= 0 and fills:
        weighted_value = 0.0
        weighted_qty = 0.0
        for fill in fills:
            fill_qty = _number(_deep_first(fill, ("quantity", "qty", "filled_quantity", "filledQuantity", "executed_quantity", "executedQuantity", "filled_qty", "filledQty")))
            fill_price = _number(_deep_first(fill, ("price", "filled_price", "filledPrice", "execution_price", "executionPrice", "average_price", "averagePrice", "avg_price", "avgPrice")))
            if fill_qty > 0 and fill_price > 0:
                weighted_value += fill_qty * fill_price
                weighted_qty += fill_qty
        if weighted_qty > 0:
            average_price = weighted_value / weighted_qty

    generic_price = _number(_deep_first(order, ("price",)))
    if "LIMIT" in normalized_type and limit_price <= 0:
        limit_price = generic_price
    if filled_quantity > 0 and average_price <= 0 and generic_price > 0 and "STOP" not in normalized_type:
        average_price = generic_price

    # Webull response objects can expose a generic price through stop-like fields.
    # A price is only a protective stop when the broker order type itself is a stop order.
    stop_price = raw_stop_price if "STOP" in normalized_type else 0.0
    if filled_quantity > 0 and average_price <= 0 and raw_stop_price > 0 and "STOP" not in normalized_type:
        average_price = raw_stop_price

    submitted_at = _time(_deep_first(order, ("submitted_at", "submittedAt", "created_at", "createdAt", "create_time", "createTime", "placed_time", "placedTime", "order_time", "orderTime")))
    filled_at = _time(_deep_first(order, ("filled_at", "filledAt", "filled_time", "filledTime", "executed_at", "executedAt", "execution_time", "executionTime", "trade_time", "tradeTime")))
    cancelled_at = _time(_deep_first(order, ("cancelled_at", "cancelledAt", "canceled_at", "canceledAt", "cancel_time", "cancelTime", "cancelled_time", "cancelledTime")))
    explicit_updated_at = _time(_deep_first(order, ("updated_at", "updatedAt", "update_time", "updateTime", "last_updated_time", "lastUpdatedTime", "modified_at", "modifiedAt")))
    if normalized_status in {"CANCELED", "CANCELLED"}:
        updated_at = cancelled_at or explicit_updated_at or submitted_at
    elif filled_quantity > 0 or normalized_status in FILLED_WORDS:
        updated_at = filled_at or explicit_updated_at or submitted_at
    else:
        updated_at = explicit_updated_at or submitted_at

    return {
        "account_id": account_id,
        "order_id": order_id,
        "client_order_id": client_order_id,
        "broker_order_id": broker_order_id,
        "symbol": _symbol(order),
        "side": side,
        "status": status,
        "order_type": order_type,
        "quantity": quantity,
        "filled_quantity": filled_quantity,
        "average_price": average_price,
        "limit_price": limit_price,
        "stop_price": stop_price,
        "submitted_at": submitted_at,
        "filled_at": filled_at,
        "cancelled_at": cancelled_at,
        "created_at": submitted_at,
        "updated_at": updated_at,
        "synced_at": utc_now(),
        "raw": order,
    }


def _valid_order(order: dict[str, Any]) -> bool:
    # Reject metadata/request IDs and empty rows. A genuine order must have an
    # order identifier plus at least one business field.
    has_id = bool(order.get("order_id"))
    has_business_data = bool(order.get("symbol") or order.get("side") or order.get("quantity") or order.get("filled_quantity"))
    return has_id and has_business_data


def _nested_execution_rows(order: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    execution_keys = {
        "executions", "execution", "fills", "fill", "filleddetails",
        "trades", "trade", "transactions", "transaction", "orderexecutions",
    }
    if isinstance(order, dict):
        for key, value in order.items():
            normalized = str(key).lower().replace("_", "")
            if normalized in execution_keys:
                if isinstance(value, list):
                    rows.extend(item for item in value if isinstance(item, dict))
                elif isinstance(value, dict):
                    rows.append(value)
            rows.extend(_nested_execution_rows(value))
    elif isinstance(order, list):
        for item in order:
            rows.extend(_nested_execution_rows(item))

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        marker = repr(sorted((str(k), str(v)) for k, v in row.items()))
        if marker not in seen:
            seen.add(marker)
            unique.append(row)
    return unique


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
        quantity = _number(_deep_first(fill, ("quantity", "qty", "filled_quantity", "filledQuantity", "executed_quantity", "executedQuantity", "filled_qty", "filledQty")), float(order.get("filled_quantity") or 0))
        price = _number(_deep_first(fill, ("price", "filled_price", "filledPrice", "execution_price", "executionPrice", "average_price", "averagePrice", "avg_price", "avgPrice")), float(order.get("average_price") or 0))
        if quantity <= 0 or price <= 0 or not symbol:
            continue
        executed_at = _time(_deep_first(fill, ("executed_at", "executedAt", "filled_time", "filledTime", "trade_time", "tradeTime", "time", "timestamp"), order.get("updated_at")))
        execution_id = str(_deep_first(fill, ("execution_id", "executionId", "trade_id", "tradeId", "fill_id", "fillId", "id"), f"{order_id}-{index}"))
        fees = _number(_deep_first(fill, ("fees", "fee", "commission", "commissions")))
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


def _is_filled_or_partial(order: dict[str, Any]) -> bool:
    status = str(order.get("status") or "").upper().replace(" ", "_").replace("-", "_")
    return status in FILLED_WORDS or float(order.get("filled_quantity") or 0) > 0


def _has_execution_data(order: dict[str, Any]) -> bool:
    if order_to_executions(order):
        return True
    return bool(
        order.get("symbol")
        and order.get("side")
        and float(order.get("filled_quantity") or 0) > 0
        and float(order.get("average_price") or 0) > 0
    )


def _detail_cache_key(account_id: str, client_order_id: str) -> str:
    return f"{account_id}:{client_order_id}"



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
                normalized_orders = [item for item in normalized_orders if _valid_order(item)]

                detail_cache = _load_detail_cache()
                detail_calls = 0
                deferred_details = 0
                detail_failures = 0

                for item in normalized_orders:
                    detail_id = str(item.get("client_order_id") or "")
                    needs_execution_detail = bool(detail_id and _is_filled_or_partial(item) and not _has_execution_data(item))
                    normalized_status = str(item.get("status") or "").upper().replace(" ", "_").replace("-", "_")
                    needs_cancel_detail = bool(
                        detail_id and normalized_status in {"CANCELED", "CANCELLED"}
                        and not item.get("cancelled_at")
                    )
                    needs_detail = needs_execution_detail or needs_cancel_detail
                    cache_key = _detail_cache_key(account_id, detail_id) if detail_id else ""

                    if needs_detail and cache_key and cache_key in detail_cache:
                        detailed = normalize_order(account_id, {"list_row": item.get("raw"), "detail": detail_cache[cache_key]})
                        if _valid_order(detailed):
                            item = detailed
                            needs_detail = not _has_execution_data(item)

                    if needs_detail and detail_calls < MAX_DETAIL_CALLS_PER_SYNC:
                        try:
                            detail = client.get_order_detail(account_id, detail_id)
                            detail_calls += 1
                            if detail:
                                detail_cache[cache_key] = detail
                                detailed = normalize_order(account_id, {"list_row": item.get("raw"), "detail": detail})
                                if _valid_order(detailed):
                                    item = detailed
                        except Exception:
                            detail_failures += 1
                    elif needs_detail:
                        deferred_details += 1

                    orders.append(item)

                _save_detail_cache(detail_cache)
                if deferred_details:
                    errors.append(
                        f"{deferred_details} filled order detail(s) were safely deferred to the next sync to stay within Webull's rate limit."
                    )
                if detail_failures:
                    errors.append(
                        f"{detail_failures} order detail request(s) could not be completed and will be retried on the next sync."
                    )
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
        broker_orders = merge_orders(load_broker_orders(), orders)
        broker_orders = link_and_classify_orders(broker_orders, trades)
        trades = refresh_trade_evidence(trades, broker_orders, all_executions)
        for trade in trades:
            build_trade_timeline(trade, broker_orders, all_executions)
            classify_trade(trade)
        save_broker_state(trades, all_executions, imports, broker_orders)

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
            "schema_version": "0.95-WEBULL-3",
            "mode": "read_only",
            "environment": environment,
            "last_sync": completed,
            "accounts": accounts,
            "balances": balances,
            "positions": positions,
            "orders": orders,
            "sync_summary": result.to_dict(),
            "diagnostics": client.diagnostics,
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

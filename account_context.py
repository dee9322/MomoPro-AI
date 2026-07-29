from __future__ import annotations

"""Canonical account context for MomoPro AI.

Every feature that needs portfolio/account information should resolve it through this
module instead of reading a page-specific Webull field or the manual risk fallback.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _number(value: Any) -> float:
    try:
        if value in (None, "") or isinstance(value, bool):
            return 0.0
        text = str(value).strip().replace(",", "").replace("$", "")
        if text.endswith("%"):
            text = text[:-1]
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _normalized_key(value: Any) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _deep_named_values(data: Any, names: Iterable[str]) -> list[Any]:
    wanted = {_normalized_key(name) for name in names}
    found: list[Any] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if _normalized_key(key) in wanted and value not in (None, ""):
                found.append(value)
            found.extend(_deep_named_values(value, names))
    elif isinstance(data, list):
        for item in data:
            found.extend(_deep_named_values(item, names))
    return found


def _positive_values(data: Any, names: Iterable[str]) -> list[float]:
    return [number for number in (_number(v) for v in _deep_named_values(data, names)) if number > 0]


def _first_positive(data: Any, names: Iterable[str]) -> float:
    values = _positive_values(data, names)
    return values[0] if values else 0.0


ACCOUNT_VALUE_KEYS = (
    "net_liquidation", "netLiquidation", "net_liquidation_value", "netLiquidationValue",
    "net_account_value", "netAccountValue", "account_value", "accountValue",
    "total_account_value", "totalAccountValue", "total_assets", "totalAssets",
    "total_asset", "totalAsset", "net_assets", "netAssets", "net_asset_value",
    "netAssetValue", "portfolio_value", "portfolioValue", "total_equity", "totalEquity",
    "account_equity", "accountEquity", "equity", "net_value", "netValue",
    "total_balance", "totalBalance", "account_balance", "accountBalance",
)
CASH_KEYS = (
    "cash_balance", "cashBalance", "cash", "cash_value", "cashValue", "total_cash",
    "totalCash", "settled_cash", "settledCash", "cash_available_for_withdrawal",
    "cashAvailableForWithdrawal",
)
MARKET_VALUE_KEYS = (
    "market_value", "marketValue", "total_market_value", "totalMarketValue",
    "positions_market_value", "positionsMarketValue", "position_market_value",
    "positionMarketValue", "stock_market_value", "stockMarketValue", "securities_value",
    "securitiesValue",
)
BUYING_POWER_KEYS = (
    "buying_power", "buyingPower", "day_buying_power", "dayBuyingPower",
    "overnight_buying_power", "overnightBuyingPower", "cash_available_for_trade",
    "cashAvailableForTrade",
)
PRICE_KEYS = ("market_price", "marketPrice", "last_price", "lastPrice", "price", "mark_price", "markPrice")
QUANTITY_KEYS = ("quantity", "qty", "position", "total_quantity", "totalQuantity", "position_qty", "positionQty")


@dataclass(frozen=True)
class AccountContext:
    account_value: float = 0.0
    cash_balance: float = 0.0
    market_value: float = 0.0
    buying_power: float = 0.0
    source: str = "Unavailable"
    broker: str = "Webull"
    account_count: int = 0
    last_sync: str | None = None
    resolved_at: str = ""
    is_live: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_webull_snapshot(snapshot: dict[str, Any] | None) -> AccountContext:
    data = snapshot if isinstance(snapshot, dict) else {}
    balances_raw = data.get("balances") or {}
    if isinstance(balances_raw, dict):
        balances = [item for item in balances_raw.values() if isinstance(item, dict)]
    elif isinstance(balances_raw, list):
        balances = [item for item in balances_raw if isinstance(item, dict)]
    else:
        balances = []

    accounts = data.get("accounts") or []
    account_count = len(accounts) if isinstance(accounts, list) else len(balances)

    # Resolve each account separately and aggregate. Never let an earlier zero-valued
    # alias hide a later positive field in the same Webull response.
    direct_values: list[float] = []
    cash_values: list[float] = []
    market_values: list[float] = []
    buying_power_values: list[float] = []
    for balance in balances:
        direct = _first_positive(balance, ACCOUNT_VALUE_KEYS)
        cash = _first_positive(balance, CASH_KEYS)
        market = _first_positive(balance, MARKET_VALUE_KEYS)
        buying_power = _first_positive(balance, BUYING_POWER_KEYS)
        if direct > 0:
            direct_values.append(direct)
        if cash > 0:
            cash_values.append(cash)
        if market > 0:
            market_values.append(market)
        if buying_power > 0:
            buying_power_values.append(buying_power)

    # Some SDK versions keep the useful values only in nested raw payloads.
    if not direct_values:
        direct_values = _positive_values(data, ACCOUNT_VALUE_KEYS)
    if not cash_values:
        cash_values = _positive_values(data, CASH_KEYS)
    if not market_values:
        market_values = _positive_values(data, MARKET_VALUE_KEYS)
    if not buying_power_values:
        buying_power_values = _positive_values(data, BUYING_POWER_KEYS)

    cash = sum(cash_values)
    market = sum(market_values)
    buying_power = sum(buying_power_values)

    # If the balance endpoint omitted market value, reconstruct it from positions.
    if market <= 0:
        reconstructed_market = 0.0
        for position in data.get("positions") or []:
            if not isinstance(position, dict):
                continue
            explicit = _first_positive(position, MARKET_VALUE_KEYS)
            if explicit > 0:
                reconstructed_market += explicit
                continue
            quantity = _first_positive(position, QUANTITY_KEYS)
            price = _first_positive(position, PRICE_KEYS)
            if quantity > 0 and price > 0:
                reconstructed_market += quantity * price
        market = reconstructed_market

    if direct_values:
        value = sum(direct_values)
        source = "Webull account equity"
    elif cash > 0 and market > 0:
        value = cash + market
        source = "Webull cash + positions"
    elif cash > 0:
        value = cash
        source = "Webull cash balance"
    elif buying_power > 0:
        value = buying_power
        source = "Webull buying power"
    else:
        value = 0.0
        source = "Unavailable"

    return AccountContext(
        account_value=value,
        cash_balance=cash,
        market_value=market,
        buying_power=buying_power,
        source=source,
        account_count=account_count,
        last_sync=str(data.get("last_sync") or "") or None,
        resolved_at=_now(),
        is_live=value > 0,
    )


def context_from_saved(value: Any) -> AccountContext:
    data = value if isinstance(value, dict) else {}
    amount = _number(data.get("account_value"))
    return AccountContext(
        account_value=amount,
        cash_balance=_number(data.get("cash_balance")),
        market_value=_number(data.get("market_value")),
        buying_power=_number(data.get("buying_power")),
        source=str(data.get("source") or ("Saved Webull account value" if amount > 0 else "Unavailable")),
        broker=str(data.get("broker") or "Webull"),
        account_count=int(_number(data.get("account_count"))),
        last_sync=str(data.get("last_sync") or "") or None,
        resolved_at=str(data.get("resolved_at") or ""),
        is_live=False,
    )

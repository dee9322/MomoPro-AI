from __future__ import annotations

"""Strictly read-only wrapper around Webull's official OpenAPI Python SDK.

Only account-list, balance, position, historical-order, open-order, and
order-detail query methods are exposed. No order-placement, modification, or
cancellation functions are implemented.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

PRODUCTION_ENDPOINT = "api.webull.com"
SANDBOX_ENDPOINT = "api.sandbox.webull.com"


class WebullConfigurationError(RuntimeError):
    pass


class WebullSDKError(RuntimeError):
    pass


class WebullAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, response_text: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


@dataclass(frozen=True)
class WebullCredentials:
    app_key: str
    app_secret: str
    region: str = "us"
    environment: str = "production"

    @property
    def endpoint(self) -> str:
        return SANDBOX_ENDPOINT if self.environment.lower() == "sandbox" else PRODUCTION_ENDPOINT

    def validate(self) -> None:
        if not self.app_key.strip() or not self.app_secret.strip():
            raise WebullConfigurationError("Webull App Key and App Secret are required in Streamlit Secrets.")


def _json_response(response: Any) -> Any:
    status = getattr(response, "status_code", None)
    text = str(getattr(response, "text", "") or "")
    if status is not None and not 200 <= int(status) < 300:
        raise WebullAPIError(
            f"Webull returned HTTP {status}. {text[:500]}",
            status_code=int(status),
            response_text=text,
        )
    try:
        return response.json()
    except Exception as error:
        if isinstance(response, (dict, list)):
            return response
        if text:
            raise WebullAPIError(f"Webull returned a non-JSON response: {text[:500]}") from error
        return response


def safe_shape(value: Any, depth: int = 0) -> Any:
    """Return keys and container sizes only; never return values or credentials."""
    if depth >= 4:
        return type(value).__name__
    if isinstance(value, dict):
        return {str(key): safe_shape(item, depth + 1) for key, item in list(value.items())[:80]}
    if isinstance(value, list):
        return {
            "type": "list",
            "count": len(value),
            "sample_shape": safe_shape(value[0], depth + 1) if value else None,
        }
    return type(value).__name__


def _dict_list_candidates(value: Any) -> list[list[dict[str, Any]]]:
    candidates: list[list[dict[str, Any]]] = []
    if isinstance(value, list):
        rows = [item for item in value if isinstance(item, dict)]
        if rows:
            candidates.append(rows)
        for item in value:
            candidates.extend(_dict_list_candidates(item))
    elif isinstance(value, dict):
        for item in value.values():
            candidates.extend(_dict_list_candidates(item))
    return candidates


def _has_any(row: dict[str, Any], names: Iterable[str]) -> bool:
    keys = {str(key).lower().replace("_", "") for key in row}
    return any(name.lower().replace("_", "") in keys for name in names)


def extract_rows(payload: Any, kind: str) -> list[dict[str, Any]]:
    """Select only genuine business rows, never arbitrary response metadata."""
    if isinstance(payload, list):
        candidates = [[item for item in payload if isinstance(item, dict)]]
    else:
        candidates = _dict_list_candidates(payload)

    signatures = {
        "account": ("account_id", "accountId", "account_type", "accountType"),
        "position": ("symbol", "instrument", "quantity", "qty", "position"),
        "order": ("client_order_id", "clientOrderId", "order_id", "orderId", "symbol", "side", "status"),
    }
    required = signatures.get(kind, ())
    scored: list[tuple[int, list[dict[str, Any]]]] = []
    for rows in candidates:
        valid = [row for row in rows if _has_any(row, required)] if required else rows
        if valid:
            score = sum(sum(1 for name in required if _has_any(row, (name,))) for row in valid)
            scored.append((score, valid))
    if not scored:
        return []
    scored.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    return scored[0][1]


def _find_cursor(payload: Any, names: Iterable[str]) -> str | None:
    normalized = {name.lower().replace("_", "") for name in names}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower().replace("_", "") in normalized and value not in (None, ""):
                return str(value)
        for value in payload.values():
            found = _find_cursor(value, names)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find_cursor(value, names)
            if found:
                return found
    return None


class WebullReadOnlyClient:
    def __init__(self, credentials: WebullCredentials):
        credentials.validate()
        self.credentials = credentials
        try:
            from webull.core.client import ApiClient
            from webull.trade.trade_client import TradeClient
        except ImportError as error:
            raise WebullSDKError(
                "The official Webull SDK is not installed. Add webull-openapi-python-sdk to requirements.txt."
            ) from error

        self.api_client = ApiClient(
            credentials.app_key.strip(), credentials.app_secret.strip(), credentials.region.strip() or "us"
        )
        self.api_client.add_endpoint(credentials.region.strip() or "us", credentials.endpoint)
        self.trade_client = TradeClient(self.api_client)
        self.diagnostics: dict[str, Any] = {}

    def _record(self, name: str, payload: Any) -> None:
        self.diagnostics[name] = safe_shape(payload)

    def get_accounts(self) -> list[dict[str, Any]]:
        payload = _json_response(self.trade_client.account_v2.get_account_list())
        self._record("accounts", payload)
        return extract_rows(payload, "account")

    def get_balance(self, account_id: str) -> dict[str, Any]:
        payload = _json_response(self.trade_client.account_v2.get_account_balance(account_id))
        self._record(f"balance_{account_id[-4:]}", payload)
        return payload if isinstance(payload, dict) else {"data": payload}

    def get_positions(self, account_id: str) -> list[dict[str, Any]]:
        # Official SDK method name is singular: get_account_position.
        payload = _json_response(self.trade_client.account_v2.get_account_position(account_id))
        self._record(f"positions_{account_id[-4:]}", payload)
        return extract_rows(payload, "position")

    def get_order_detail(self, account_id: str, client_order_id: str) -> dict[str, Any]:
        payload = _json_response(self.trade_client.order_v2.get_order_detail(account_id, client_order_id))
        self._record(f"order_detail_{client_order_id[-8:]}", payload)
        return payload if isinstance(payload, dict) else {"data": payload}

    def get_orders(
        self,
        account_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page_size: int = 100,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        end_time = end_time or datetime.now(timezone.utc)
        start_time = start_time or (end_time - timedelta(days=730))
        start_date = start_time.strftime("%Y-%m-%d")
        end_date = end_time.strftime("%Y-%m-%d")

        rows: list[dict[str, Any]] = []
        last_client_order_id: str | None = None
        last_order_id: str | None = None
        seen_cursors: set[tuple[str | None, str | None]] = set()

        for page in range(max_pages):
            payload = _json_response(
                self.trade_client.order_v2.get_order_history(
                    account_id,
                    page_size=page_size,
                    start_date=start_date,
                    end_date=end_date,
                    last_client_order_id=last_client_order_id,
                    last_order_id=last_order_id,
                )
            )
            self._record(f"orders_{account_id[-4:]}_page_{page + 1}", payload)
            page_rows = extract_rows(payload, "order")
            if not page_rows:
                break
            rows.extend(page_rows)

            next_client = _find_cursor(payload, ("last_client_order_id", "lastClientOrderId", "next_client_order_id"))
            next_order = _find_cursor(payload, ("last_order_id", "lastOrderId", "next_order_id"))
            cursor = (next_client, next_order)
            if cursor == (None, None) or cursor in seen_cursors:
                break
            seen_cursors.add(cursor)
            last_client_order_id, last_order_id = cursor
            if len(page_rows) < page_size:
                break

        # De-duplicate while preserving order.
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            key = str(
                row.get("client_order_id")
                or row.get("clientOrderId")
                or row.get("order_id")
                or row.get("orderId")
                or repr(sorted(row.items()))
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return unique

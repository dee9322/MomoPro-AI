from __future__ import annotations

"""Thin, read-only wrapper around Webull's official OpenAPI Python SDK.

This module intentionally exposes only GET/query operations. No place, replace,
or cancel order methods are implemented anywhere in MomoPro AI.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import inspect
from typing import Any, Callable, Iterable


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
            raise WebullConfigurationError(
                "Webull App Key and App Secret are required in Streamlit Secrets."
            )


def _json_response(response: Any) -> Any:
    status = getattr(response, "status_code", None)
    if status is not None and not 200 <= int(status) < 300:
        text = str(getattr(response, "text", "") or "")
        raise WebullAPIError(
            f"Webull returned HTTP {status}. {text[:500]}",
            status_code=int(status),
            response_text=text,
        )
    try:
        return response.json()
    except Exception as error:
        text = str(getattr(response, "text", "") or "")
        if text:
            raise WebullAPIError(f"Webull returned a non-JSON response: {text[:500]}") from error
        return response


def _call_with_supported_kwargs(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a changing SDK method while passing only parameters it supports."""
    try:
        signature = inspect.signature(func)
        accepts_kwargs = any(
            item.kind == inspect.Parameter.VAR_KEYWORD
            for item in signature.parameters.values()
        )
        clean_kwargs = kwargs if accepts_kwargs else {
            key: value for key, value in kwargs.items() if key in signature.parameters
        }
    except (TypeError, ValueError):
        clean_kwargs = kwargs
    return func(*args, **clean_kwargs)




def _call_account_method(func: Callable[..., Any], account_id: str, **kwargs: Any) -> Any:
    try:
        return _call_with_supported_kwargs(func, account_id, **kwargs)
    except TypeError as positional_error:
        try:
            return _call_with_supported_kwargs(func, account_id=account_id, **kwargs)
        except TypeError:
            raise positional_error


def _call_order_detail_method(func: Callable[..., Any], account_id: str, order_id: str) -> Any:
    try:
        return _call_with_supported_kwargs(func, account_id, order_id)
    except TypeError as positional_error:
        try:
            return _call_with_supported_kwargs(func, account_id=account_id, order_id=order_id)
        except TypeError:
            raise positional_error

def _resolve_method(objects: Iterable[Any], names: Iterable[str]) -> Callable[..., Any] | None:
    for obj in objects:
        if obj is None:
            continue
        for name in names:
            method = getattr(obj, name, None)
            if callable(method):
                return method
    return None


class WebullReadOnlyClient:
    """Official Webull SDK client restricted to account-query operations."""

    def __init__(self, credentials: WebullCredentials):
        credentials.validate()
        self.credentials = credentials
        try:
            from webull.core.client import ApiClient
            from webull.trade.trade_client import TradeClient
        except ImportError as error:
            raise WebullSDKError(
                "The official Webull SDK is not installed. Add "
                "'webull-openapi-python-sdk' to requirements.txt and redeploy."
            ) from error

        self.api_client = ApiClient(
            credentials.app_key.strip(),
            credentials.app_secret.strip(),
            credentials.region.strip() or "us",
        )
        self.api_client.add_endpoint(
            credentials.region.strip() or "us",
            credentials.endpoint,
        )
        self.trade_client = TradeClient(self.api_client)

    def _modules(self, *names: str) -> list[Any]:
        modules = [self.trade_client]
        modules.extend(getattr(self.trade_client, name, None) for name in names)
        return modules

    def get_accounts(self) -> list[dict[str, Any]]:
        method = _resolve_method(
            self._modules("account_v2", "account"),
            ("get_account_list", "account_list", "get_accounts"),
        )
        if method is None:
            raise WebullSDKError("The installed Webull SDK does not expose account-list queries.")
        payload = _json_response(method())
        return _extract_rows(payload, preferred=("accounts", "account_list", "data"))

    def get_balance(self, account_id: str) -> dict[str, Any]:
        method = _resolve_method(
            self._modules("account_v2", "account", "asset_v2", "asset"),
            ("get_account_balance", "get_balance", "account_balance"),
        )
        if method is None:
            raise WebullSDKError("The installed Webull SDK does not expose account-balance queries.")
        payload = _json_response(_call_account_method(method, account_id))
        rows = _extract_rows(payload, preferred=("balances", "assets", "data"))
        return rows[0] if len(rows) == 1 else (payload if isinstance(payload, dict) else {"items": rows})

    def get_positions(self, account_id: str) -> list[dict[str, Any]]:
        method = _resolve_method(
            self._modules("account_v2", "account", "asset_v2", "asset"),
            ("get_account_positions", "get_positions", "account_positions"),
        )
        if method is None:
            raise WebullSDKError("The installed Webull SDK does not expose account-position queries.")
        payload = _json_response(_call_account_method(method, account_id))
        return _extract_rows(payload, preferred=("positions", "holdings", "data"))

    def get_orders(
        self,
        account_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch order history using the newest compatible read method in the SDK.

        Webull has renamed order-query methods across SDK revisions. This uses
        introspection and several official naming generations without ever
        invoking write methods.
        """
        method = _resolve_method(
            self._modules("order_v3", "order_v2", "order"),
            (
                "get_order_list",
                "get_orders",
                "query_orders",
                "get_order_history",
                "order_list",
            ),
        )
        if method is None:
            raise WebullSDKError("The installed Webull SDK does not expose order-list queries.")

        end_time = end_time or datetime.now(timezone.utc)
        start_time = start_time or (end_time - timedelta(days=730))
        formats = {
            "start_time": start_time.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "end_time": end_time.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "start_date": start_time.strftime("%Y-%m-%d"),
            "end_date": end_time.strftime("%Y-%m-%d"),
            "page_size": page_size,
            "limit": page_size,
        }
        response = _call_account_method(method, account_id, **formats)
        payload = _json_response(response)
        return _extract_rows(payload, preferred=("orders", "order_list", "data", "items"))

    def get_order_detail(self, account_id: str, order_id: str) -> dict[str, Any]:
        method = _resolve_method(
            self._modules("order_v3", "order_v2", "order"),
            ("get_order_detail", "order_detail", "get_detail"),
        )
        if method is None:
            return {}
        response = _call_order_detail_method(method, account_id, order_id)
        payload = _json_response(response)
        return payload if isinstance(payload, dict) else {"data": payload}


def _extract_rows(payload: Any, preferred: Iterable[str] = ()) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in preferred:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_rows(value, preferred=preferred)
            if nested:
                return nested
            return [value]

    for key in ("data", "result", "items", "list", "rows"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_rows(value, preferred=preferred)
            if nested:
                return nested

    # A single-object response is still a valid row.
    return [payload] if payload else []

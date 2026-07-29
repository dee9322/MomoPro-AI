from __future__ import annotations

from typing import Any

from cloud_storage import load_document, save_document

BUCKET = "workspace_state"
DEFAULT_WORKSPACE = {
    "schema_version": "0.98.2",
    "active_page": "Dashboard",
    "selected_symbol": None,
    "active_watchlist": "Main Watchlist",
    "news_search_symbol": "SPY",
    "chart_symbol": "SPY",
    "chart_timeframe": "1D",
    "chart_candles": 300,
    "chart_overlays": [],
    "dashboard_universe": "Entire Market",
    "scanner_filters": {},
    "scanner_sort": {},
    "trade_plan_prefill": {},
    "journal_prefill": {},
    "expanded_sections": [],
    "last_webull_sync": None,
}


def _dictionary(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def normalize_workspace(workspace: dict[str, Any] | None) -> dict[str, Any]:
    source = _dictionary(workspace)
    clean = dict(DEFAULT_WORKSPACE)
    clean.update(source)

    clean["schema_version"] = "0.98.2"
    clean["active_page"] = str(clean.get("active_page") or "Dashboard")
    clean["selected_symbol"] = str(clean.get("selected_symbol") or "").upper().strip() or None
    clean["active_watchlist"] = str(clean.get("active_watchlist") or "Main Watchlist")
    clean["news_search_symbol"] = str(clean.get("news_search_symbol") or "").upper().strip()
    clean["chart_symbol"] = str(clean.get("chart_symbol") or clean.get("selected_symbol") or "SPY").upper().strip()
    clean["chart_timeframe"] = str(clean.get("chart_timeframe") or "1D")
    try:
        clean["chart_candles"] = int(clean.get("chart_candles") or 300)
    except (TypeError, ValueError):
        clean["chart_candles"] = 300
    clean["chart_overlays"] = _list(clean.get("chart_overlays"))
    clean["scanner_filters"] = _dictionary(clean.get("scanner_filters"))
    clean["scanner_sort"] = _dictionary(clean.get("scanner_sort"))
    clean["trade_plan_prefill"] = _dictionary(clean.get("trade_plan_prefill"))
    clean["journal_prefill"] = _dictionary(clean.get("journal_prefill"))
    clean["expanded_sections"] = _list(clean.get("expanded_sections"))
    return clean


def load_workspace() -> dict[str, Any]:
    payload = load_document(BUCKET, DEFAULT_WORKSPACE)
    return normalize_workspace(payload if isinstance(payload, dict) else {})


def save_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    clean = normalize_workspace(workspace)
    save_document(BUCKET, clean)
    return clean

from __future__ import annotations

from typing import Any

from cloud_storage import load_document, save_document

BUCKET = "workspace_state"
DEFAULT_WORKSPACE = {
    "active_page": "Dashboard",
    "selected_symbol": None,
    "active_watchlist": "Main Watchlist",
    "news_search_symbol": "SPY",
    "chart_symbol": "SPY",
    "chart_timeframe": "1D",
    "scanner_filters": {},
    "expanded_sections": [],
}


def load_workspace() -> dict[str, Any]:
    payload = load_document(BUCKET, DEFAULT_WORKSPACE)
    merged = dict(DEFAULT_WORKSPACE)
    if isinstance(payload, dict):
        merged.update(payload)
    return merged


def save_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    clean = dict(DEFAULT_WORKSPACE)
    clean.update(workspace or {})
    save_document(BUCKET, clean)
    return clean

from __future__ import annotations

from typing import Any

from cloud_storage import load_document, save_document

BUCKET = "workspace_state"
DEFAULT_WORKSPACE = {
    "schema_version": "0.98.2",
    "active_page": "Dashboard",
    "active_tab_id": "page:dashboard",
    "workspace_tabs": [],
    "selected_symbol": None,
    "active_watchlist": "Main Watchlist",
    "news_search_symbol": "SPY",
    "chart_symbol": None,
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
    clean["active_tab_id"] = str(clean.get("active_tab_id") or "page:dashboard")
    clean["workspace_tabs"] = [dict(item) for item in _list(clean.get("workspace_tabs")) if isinstance(item, dict)]
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


def persist_session_workspace() -> dict[str, Any]:
    """Persist navigation and workspace state without optional-service dependencies.

    This function is intentionally limited to session/workspace fields. A Webull read,
    chart-data request, or any other optional integration must never be able to block
    page, ticker, tab, or settings recovery.
    """
    try:
        import streamlit as st

        selected_symbol = str(st.session_state.get("selected_symbol") or "").upper().strip() or None
        chart_symbol = str(
            st.session_state.get("live_chart_symbol")
            or selected_symbol
            or "SPY"
        ).upper().strip()
        workspace = dict(st.session_state.get("momopro_workspace") or {})
        workspace.update({
            "active_page": st.session_state.get("active_page", "Dashboard"),
            "active_tab_id": st.session_state.get("active_tab_id", "page:dashboard"),
            "workspace_tabs": st.session_state.get("workspace_tabs", []),
            "selected_symbol": selected_symbol,
            "news_search_symbol": st.session_state.get("news_search_symbol", ""),
            "active_watchlist": st.session_state.get("active_watchlist", "Main Watchlist"),
            "dashboard_universe": st.session_state.get("dashboard_universe", "Entire Market"),
            "chart_symbol": chart_symbol,
            "chart_timeframe": st.session_state.get("live_chart_timeframe", "1D"),
            "chart_candles": st.session_state.get("live_chart_candles", 300),
            "chart_overlays": st.session_state.get("live_chart_overlays", []),
            "trade_plan_prefill": st.session_state.get("trade_plan_prefill", {}),
            "journal_prefill": st.session_state.get("journal_prefill", {}),
        })
        clean = save_workspace(workspace)
        st.session_state.momopro_workspace = clean
        st.session_state._workspace_persist_error = ""
        return clean
    except Exception as error:
        try:
            import streamlit as st
            st.session_state._workspace_persist_error = str(error)
        except Exception:
            pass
        return normalize_workspace({})

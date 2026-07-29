from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

import streamlit as st


@dataclass(frozen=True)
class PageRoute:
    label: str
    slug: str


ROUTES: tuple[PageRoute, ...] = (
    PageRoute("Dashboard", "dashboard"),
    PageRoute("Market Context", "market-context"),
    PageRoute("Scanner", "scanner"),
    PageRoute("News", "news"),
    PageRoute("AI Analysis", "ai-analysis"),
    PageRoute("Watchlist", "watchlist"),
    PageRoute("Trade Planner", "trade-planner"),
    PageRoute("Journal", "journal"),
    PageRoute("Performance", "performance"),
    PageRoute("Learning", "learning"),
    PageRoute("Settings", "settings"),
    PageRoute("Live Chart", "live-chart"),
)

_LABEL_TO_SLUG = {route.label: route.slug for route in ROUTES}
_SLUG_TO_LABEL = {route.slug: route.label for route in ROUTES}
PAGE_LABELS = tuple(route.label for route in ROUTES)
DEFAULT_PAGE = "Dashboard"
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,15}$")


def normalize_page(value: Any) -> str:
    text = str(value or "").strip()
    if text in _LABEL_TO_SLUG:
        return text
    slug = text.lower().strip("/").replace("_", "-").replace(" ", "-")
    return _SLUG_TO_LABEL.get(slug, DEFAULT_PAGE)


def page_slug(label: str) -> str:
    return _LABEL_TO_SLUG.get(normalize_page(label), _LABEL_TO_SLUG[DEFAULT_PAGE])


def normalize_symbol(value: Any) -> str:
    symbol = str(value or "").upper().strip()
    symbol = symbol.replace("$", "").replace(" ", "")
    return symbol if _SYMBOL_PATTERN.fullmatch(symbol) else ""


def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        return ""
    if isinstance(value, list):
        return str(value[0] if value else "")
    return str(value or "")


def _write_query(page: str, symbol: str) -> None:
    try:
        st.query_params["page"] = page_slug(page)
        if symbol:
            st.query_params["symbol"] = symbol
        elif "symbol" in st.query_params:
            del st.query_params["symbol"]
    except Exception:
        # Workspace persistence remains the fallback when query parameters are
        # unavailable in a future or alternate Streamlit runtime.
        return


def initialize_navigation(workspace: dict[str, Any] | None = None) -> None:
    workspace = workspace or {}
    query_page = normalize_page(_query_value("page")) if _query_value("page") else ""
    query_symbol = normalize_symbol(_query_value("symbol"))

    if "active_page" not in st.session_state:
        st.session_state.active_page = query_page or normalize_page(workspace.get("active_page"))
    elif query_page and query_page != st.session_state.active_page:
        st.session_state.active_page = query_page

    saved_symbol = normalize_symbol(workspace.get("selected_symbol"))
    current_symbol = normalize_symbol(st.session_state.get("selected_symbol"))
    if query_symbol:
        st.session_state.selected_symbol = query_symbol
    elif not current_symbol and saved_symbol:
        st.session_state.selected_symbol = saved_symbol

    active_symbol = normalize_symbol(st.session_state.get("selected_symbol"))
    _write_query(st.session_state.active_page, active_symbol)


def set_active_symbol(symbol: Any, *, sync_related: bool = True) -> str:
    clean = normalize_symbol(symbol)
    if not clean:
        return ""
    st.session_state.selected_symbol = clean
    if sync_related:
        st.session_state.news_search_symbol = clean
        st.session_state.ai_analysis_symbol = clean
        st.session_state.live_chart_symbol = clean
        st.session_state.planner_symbol = clean
        st.session_state.journal_new_symbol = clean
    _write_query(st.session_state.get("active_page", DEFAULT_PAGE), clean)
    return clean


def navigate_to(page: str, *, symbol: Any | None = None, rerun: bool = True) -> None:
    target = normalize_page(page)
    st.session_state.active_page = target
    st.session_state.navigation_page_picker = target
    if symbol is not None:
        set_active_symbol(symbol)
    else:
        _write_query(target, normalize_symbol(st.session_state.get("selected_symbol")))
    if rerun:
        st.rerun()


def _navigation_changed() -> None:
    navigate_to(st.session_state.navigation_page_picker)


def _symbol_submitted() -> None:
    clean = set_active_symbol(st.session_state.get("global_symbol_search"))
    if clean:
        st.session_state.global_symbol_search = clean


def sync_symbol_widget(widget_key: str) -> None:
    clean = normalize_symbol(st.session_state.get(widget_key))
    if not clean:
        return
    st.session_state.selected_symbol = clean
    st.session_state.news_search_symbol = clean
    st.session_state.ai_analysis_symbol = clean
    if widget_key != "live_chart_symbol":
        st.session_state.live_chart_symbol = clean
    if widget_key != "planner_symbol":
        st.session_state.planner_symbol = clean
    if widget_key != "journal_new_symbol":
        st.session_state.journal_new_symbol = clean
    _write_query(st.session_state.get("active_page", DEFAULT_PAGE), clean)


def render_navigation() -> None:
    active_page = normalize_page(st.session_state.get("active_page"))
    if st.session_state.get("navigation_page_picker") != active_page:
        st.session_state.navigation_page_picker = active_page

    with st.sidebar:
        st.markdown("### MomoPro AI")
        st.radio(
            "Navigation",
            PAGE_LABELS,
            key="navigation_page_picker",
            on_change=_navigation_changed,
            label_visibility="collapsed",
        )
        st.divider()
        if "global_symbol_search" not in st.session_state:
            st.session_state.global_symbol_search = normalize_symbol(st.session_state.get("selected_symbol"))
        st.text_input(
            "Universal ticker",
            key="global_symbol_search",
            placeholder="AAPL",
            on_change=_symbol_submitted,
            help="Updates the shared ticker context used across MomoPro AI.",
        )
        active_symbol = normalize_symbol(st.session_state.get("selected_symbol"))
        st.caption(f"Active ticker: **{active_symbol or 'None selected'}**")


def active_page_is(page: str) -> bool:
    return normalize_page(st.session_state.get("active_page")) == normalize_page(page)


def build_deep_link(page: str, symbol: Any | None = None) -> str:
    query = f"?page={page_slug(page)}"
    clean = normalize_symbol(symbol)
    if clean:
        query += f"&symbol={clean}"
    return query


def first_positive(values: Iterable[Any]) -> float:
    for value in values:
        try:
            number = float(value or 0)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return 0.0

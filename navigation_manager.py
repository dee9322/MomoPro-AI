from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

import streamlit as st

from workspace_storage import persist_session_workspace


@dataclass(frozen=True)
class PageRoute:
    label: str
    slug: str
    icon: str


ROUTES: tuple[PageRoute, ...] = (
    PageRoute("Dashboard", "dashboard", "📊"),
    PageRoute("Market Context", "market-context", "🌎"),
    PageRoute("Scanner", "scanner", "🔎"),
    PageRoute("News", "news", "📰"),
    PageRoute("AI Analysis", "ai-analysis", "🤖"),
    PageRoute("Watchlist", "watchlist", "⭐"),
    PageRoute("Trade Planner", "trade-planner", "📝"),
    PageRoute("Journal", "journal", "📔"),
    PageRoute("Performance", "performance", "📈"),
    PageRoute("Learning", "learning", "🎓"),
    PageRoute("Settings", "settings", "⚙️"),
    PageRoute("Live Chart", "live-chart", "📉"),
)

_LABEL_TO_SLUG = {route.label: route.slug for route in ROUTES}
_SLUG_TO_LABEL = {route.slug: route.label for route in ROUTES}
_LABEL_TO_ICON = {route.label: route.icon for route in ROUTES}
PAGE_LABELS = tuple(route.label for route in ROUTES)
DEFAULT_PAGE = "Dashboard"
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,15}$")
MAX_STOCK_TABS = 12


def normalize_page(value: Any) -> str:
    text = str(value or "").strip()
    if text in _LABEL_TO_SLUG:
        return text
    slug = text.lower().strip("/").replace("_", "-").replace(" ", "-")
    return _SLUG_TO_LABEL.get(slug, DEFAULT_PAGE)


def page_slug(label: str) -> str:
    return _LABEL_TO_SLUG.get(normalize_page(label), _LABEL_TO_SLUG[DEFAULT_PAGE])


def normalize_symbol(value: Any) -> str:
    symbol = str(value or "").upper().strip().replace("$", "").replace(" ", "")
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
        return


def _page_tab_id(page: str) -> str:
    return f"page:{page_slug(page)}"


def _stock_tab_id(symbol: str) -> str:
    return f"stock:{normalize_symbol(symbol)}"


def _clean_stock_tab(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    symbol = normalize_symbol(raw.get("symbol") or (raw.get("label") if raw.get("kind") == "stock" else ""))
    if not symbol:
        return None
    return {
        "id": _stock_tab_id(symbol),
        "kind": "stock",
        "label": symbol,
        "page": "Scanner",
        "symbol": symbol,
        "closable": True,
    }


def _ensure_stock_tabs() -> None:
    tabs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in st.session_state.get("workspace_tabs", []):
        tab = _clean_stock_tab(raw)
        if tab and tab["id"] not in seen:
            tabs.append(tab)
            seen.add(tab["id"])
    st.session_state.workspace_tabs = tabs[-MAX_STOCK_TABS:]


def _stock_tab_by_id(tab_id: str) -> dict[str, Any] | None:
    for tab in st.session_state.get("workspace_tabs", []):
        if tab.get("id") == tab_id:
            return tab
    return None


def initialize_navigation(workspace: dict[str, Any] | None = None) -> None:
    workspace = workspace or {}
    query_page_text = _query_value("page")
    query_page = normalize_page(query_page_text) if query_page_text else ""
    query_symbol = normalize_symbol(_query_value("symbol"))

    if "workspace_tabs" not in st.session_state:
        st.session_state.workspace_tabs = list(workspace.get("workspace_tabs") or [])
    _ensure_stock_tabs()

    if "active_page" not in st.session_state:
        st.session_state.active_page = query_page or normalize_page(workspace.get("active_page"))
    elif query_page and query_page != normalize_page(st.session_state.active_page):
        st.session_state.active_page = query_page

    saved_symbol = normalize_symbol(workspace.get("selected_symbol"))
    current_symbol = normalize_symbol(st.session_state.get("selected_symbol"))
    if query_symbol:
        st.session_state.selected_symbol = query_symbol
    elif not current_symbol and saved_symbol:
        st.session_state.selected_symbol = saved_symbol

    saved_active_tab = str(workspace.get("active_tab_id") or "")
    if "active_tab_id" not in st.session_state:
        st.session_state.active_tab_id = saved_active_tab or _page_tab_id(st.session_state.active_page)

    if query_symbol and normalize_page(st.session_state.active_page) == "Scanner":
        open_stock_workspace(query_symbol, rerun=False)
    elif str(st.session_state.active_tab_id).startswith("stock:"):
        tab = _stock_tab_by_id(str(st.session_state.active_tab_id))
        if tab:
            st.session_state.active_page = "Scanner"
            set_active_symbol(tab.get("symbol"))
        else:
            st.session_state.active_tab_id = _page_tab_id(st.session_state.active_page)
    else:
        st.session_state.active_tab_id = _page_tab_id(st.session_state.active_page)

    _write_query(st.session_state.active_page, normalize_symbol(st.session_state.get("selected_symbol")))


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


def _request_navigation_sync(page: str) -> None:
    # Do not mutate the radio widget's key after it has been instantiated.
    # The next script run applies this value before rendering the widget.
    st.session_state._navigation_sync_page = normalize_page(page)


def open_page_tab(page: str, *, symbol: Any | None = None, rerun: bool = True) -> None:
    target = normalize_page(page)
    st.session_state.active_page = target
    st.session_state.active_tab_id = _page_tab_id(target)
    _request_navigation_sync(target)
    if symbol is not None:
        set_active_symbol(symbol)
    else:
        _write_query(target, normalize_symbol(st.session_state.get("selected_symbol")))
    persist_session_workspace()
    if rerun:
        st.rerun()


def open_stock_workspace(symbol: Any, *, rerun: bool = True) -> str:
    clean = set_active_symbol(symbol)
    if not clean:
        return ""
    _ensure_stock_tabs()
    tab_id = _stock_tab_id(clean)
    if not _stock_tab_by_id(tab_id):
        st.session_state.workspace_tabs.append(_clean_stock_tab({"kind": "stock", "symbol": clean}))
        st.session_state.workspace_tabs = st.session_state.workspace_tabs[-MAX_STOCK_TABS:]
    st.session_state.active_tab_id = tab_id
    st.session_state.active_page = "Scanner"
    _request_navigation_sync("Scanner")
    _write_query("Scanner", clean)
    persist_session_workspace()
    if rerun:
        st.rerun()
    return clean


def navigate_to(page: str, *, symbol: Any | None = None, rerun: bool = True) -> None:
    open_page_tab(page, symbol=symbol, rerun=rerun)


def activate_tab(tab_id: str, *, rerun: bool = True) -> None:
    if tab_id.startswith("page:"):
        slug = tab_id.split(":", 1)[1]
        open_page_tab(_SLUG_TO_LABEL.get(slug, DEFAULT_PAGE), rerun=rerun)
        return
    tab = _stock_tab_by_id(tab_id)
    if not tab:
        return
    st.session_state.active_tab_id = tab_id
    st.session_state.active_page = "Scanner"
    _request_navigation_sync("Scanner")
    set_active_symbol(tab.get("symbol"))
    persist_session_workspace()
    if rerun:
        st.rerun()


def close_tab(tab_id: str, *, rerun: bool = True) -> None:
    _ensure_stock_tabs()
    tabs = st.session_state.workspace_tabs
    index = next((i for i, tab in enumerate(tabs) if tab.get("id") == tab_id), None)
    if index is None:
        return
    was_active = st.session_state.get("active_tab_id") == tab_id
    tabs.pop(index)
    st.session_state.workspace_tabs = tabs
    if was_active:
        st.session_state.active_page = "Scanner"
        st.session_state.active_tab_id = _page_tab_id("Scanner")
        _request_navigation_sync("Scanner")
        if tabs:
            st.session_state.selected_symbol = normalize_symbol(tabs[-1].get("symbol")) or None
        _write_query("Scanner", normalize_symbol(st.session_state.get("selected_symbol")))
    persist_session_workspace()
    if rerun:
        st.rerun()


def close_active_stock_tab(*, rerun: bool = True) -> None:
    tab_id = str(st.session_state.get("active_tab_id") or "")
    if tab_id.startswith("stock:"):
        close_tab(tab_id, rerun=rerun)
        return
    st.session_state.selected_symbol = None
    if rerun:
        st.rerun()


def _navigation_changed() -> None:
    # Widget callbacks already trigger a rerun; no explicit st.rerun here.
    target = normalize_page(st.session_state.navigation_page_picker)
    st.session_state.active_page = target
    st.session_state.active_tab_id = _page_tab_id(target)
    _write_query(target, normalize_symbol(st.session_state.get("selected_symbol")))
    persist_session_workspace()


def _symbol_submitted() -> None:
    clean = normalize_symbol(st.session_state.get("global_symbol_search"))
    if clean:
        st.session_state.global_symbol_search = clean
        open_stock_workspace(clean, rerun=False)


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
    persist_session_workspace()


def render_navigation() -> None:
    active_page = normalize_page(st.session_state.get("active_page"))
    pending_page = normalize_page(st.session_state.pop("_navigation_sync_page", active_page))
    # This assignment occurs before the widget is instantiated on this run.
    if st.session_state.get("navigation_page_picker") != pending_page:
        st.session_state.navigation_page_picker = pending_page

    with st.sidebar:
        st.markdown("### MomoPro AI")
        st.caption("Navigation")
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
            help="Opens a reusable stock workspace tab and updates the shared ticker context.",
        )
        active_symbol = normalize_symbol(st.session_state.get("selected_symbol"))
        st.caption(f"Active ticker: **{active_symbol or 'None selected'}**")


def _render_stock_workspace_tabs() -> None:
    _ensure_stock_tabs()
    tabs = st.session_state.workspace_tabs
    if not tabs:
        return

    active_id = str(st.session_state.get("active_tab_id") or "")
    st.markdown('<div class="momopro-stock-caption">OPEN STOCKS</div>', unsafe_allow_html=True)
    for row_start in range(0, len(tabs), 6):
        row_tabs = tabs[row_start:row_start + 6]
        weights: list[float] = []
        for _tab in row_tabs:
            weights.extend([4.0, 0.75])
        columns = st.columns(weights, gap="small")
        column_index = 0
        for tab in row_tabs:
            with columns[column_index]:
                if st.button(
                    f"📄 {tab['label']}",
                    key=f"stock_workspace_tab_{tab['id']}",
                    type="primary" if tab["id"] == active_id else "secondary",
                    width="stretch",
                ):
                    activate_tab(tab["id"])
            column_index += 1
            with columns[column_index]:
                if st.button("×", key=f"close_stock_workspace_tab_{tab['id']}", help=f"Close {tab['label']}"):
                    close_tab(tab["id"])
            column_index += 1
    st.divider()


def _render_page_tabs() -> None:
    active_page = normalize_page(st.session_state.get("active_page"))
    st.markdown('<div class="momopro-page-caption">MOMOPRO AI</div>', unsafe_allow_html=True)
    # All product sections remain visible, matching the original tab workflow.
    for row_start in range(0, len(ROUTES), 6):
        row_routes = ROUTES[row_start:row_start + 6]
        columns = st.columns(len(row_routes), gap="small")
        for column, route in zip(columns, row_routes):
            with column:
                if st.button(
                    f"{route.icon} {route.label}",
                    key=f"main_page_tab_{route.slug}",
                    type="primary" if route.label == active_page else "secondary",
                    width="stretch",
                ):
                    open_page_tab(route.label)
    st.divider()


def render_workspace_tabs() -> None:
    """Render two intentionally separate tab layers.

    Stock workspaces live at the very top and are closeable. The full set of
    permanent MomoPro page tabs sits beneath them. The sidebar remains as a
    second permanent navigation path.
    """
    st.markdown(
        """
        <style>
        .momopro-stock-caption,
        .momopro-page-caption {
            color: rgba(250,250,250,.58);
            font-size: .75rem;
            letter-spacing: .08em;
            margin: 0 0 .3rem 0;
        }
        div[data-testid="stHorizontalBlock"] { gap: .3rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _render_stock_workspace_tabs()
    _render_page_tabs()


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

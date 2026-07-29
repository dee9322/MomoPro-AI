from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

import streamlit as st


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
MAX_WORKSPACE_TABS = 14


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
        return


def _page_tab_id(page: str) -> str:
    return f"page:{page_slug(page)}"


def _stock_tab_id(symbol: str) -> str:
    return f"stock:{normalize_symbol(symbol)}"


def _clean_tab(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "page")
    if kind == "stock":
        symbol = normalize_symbol(raw.get("symbol"))
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
    page = normalize_page(raw.get("page") or raw.get("label"))
    return {
        "id": _page_tab_id(page),
        "kind": "page",
        "label": page,
        "page": page,
        "symbol": "",
        "closable": page != "Dashboard",
    }


def _default_tabs() -> list[dict[str, Any]]:
    return [
        _clean_tab({"kind": "page", "page": "Dashboard"}),
        _clean_tab({"kind": "page", "page": "Scanner"}),
    ]


def _ensure_tabs() -> None:
    tabs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in st.session_state.get("workspace_tabs", []):
        tab = _clean_tab(raw)
        if tab and tab["id"] not in seen:
            tabs.append(tab)
            seen.add(tab["id"])
    for tab in _default_tabs():
        if tab and tab["id"] not in seen:
            tabs.insert(0 if tab["page"] == "Dashboard" else len(tabs), tab)
            seen.add(tab["id"])
    st.session_state.workspace_tabs = tabs[:MAX_WORKSPACE_TABS]


def _tab_by_id(tab_id: str) -> dict[str, Any] | None:
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
    _ensure_tabs()

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

    saved_active_tab = str(workspace.get("active_tab_id") or "")
    if "active_tab_id" not in st.session_state:
        st.session_state.active_tab_id = saved_active_tab

    # Deep links to a stock become a stock workspace tab. Normal page links
    # become regular workspace tabs.
    if query_symbol and normalize_page(st.session_state.active_page) == "Scanner":
        open_stock_workspace(query_symbol, rerun=False)
    else:
        open_page_tab(st.session_state.active_page, rerun=False)

    if not _tab_by_id(str(st.session_state.get("active_tab_id") or "")):
        st.session_state.active_tab_id = _page_tab_id(st.session_state.active_page)

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


def open_page_tab(page: str, *, symbol: Any | None = None, rerun: bool = True) -> None:
    target = normalize_page(page)
    _ensure_tabs()
    tab_id = _page_tab_id(target)
    if not _tab_by_id(tab_id):
        st.session_state.workspace_tabs.append(_clean_tab({"kind": "page", "page": target}))
        st.session_state.workspace_tabs = st.session_state.workspace_tabs[-MAX_WORKSPACE_TABS:]
    st.session_state.active_tab_id = tab_id
    st.session_state.active_page = target
    st.session_state.navigation_page_picker = target
    if symbol is not None:
        set_active_symbol(symbol)
    else:
        _write_query(target, normalize_symbol(st.session_state.get("selected_symbol")))
    if rerun:
        st.rerun()


def open_stock_workspace(symbol: Any, *, rerun: bool = True) -> str:
    clean = set_active_symbol(symbol)
    if not clean:
        return ""
    _ensure_tabs()
    tab_id = _stock_tab_id(clean)
    if not _tab_by_id(tab_id):
        st.session_state.workspace_tabs.append(_clean_tab({"kind": "stock", "symbol": clean}))
        # Preserve Dashboard while trimming the oldest closeable workspace tab.
        while len(st.session_state.workspace_tabs) > MAX_WORKSPACE_TABS:
            removable = next((i for i, tab in enumerate(st.session_state.workspace_tabs) if tab.get("closable")), None)
            if removable is None:
                break
            st.session_state.workspace_tabs.pop(removable)
    st.session_state.active_tab_id = tab_id
    st.session_state.active_page = "Scanner"
    st.session_state.navigation_page_picker = "Scanner"
    _write_query("Scanner", clean)
    if rerun:
        st.rerun()
    return clean


def navigate_to(page: str, *, symbol: Any | None = None, rerun: bool = True) -> None:
    open_page_tab(page, symbol=symbol, rerun=rerun)


def activate_tab(tab_id: str, *, rerun: bool = True) -> None:
    tab = _tab_by_id(tab_id)
    if not tab:
        return
    st.session_state.active_tab_id = tab_id
    st.session_state.active_page = normalize_page(tab.get("page"))
    st.session_state.navigation_page_picker = st.session_state.active_page
    if tab.get("kind") == "stock":
        set_active_symbol(tab.get("symbol"))
    else:
        _write_query(st.session_state.active_page, normalize_symbol(st.session_state.get("selected_symbol")))
    if rerun:
        st.rerun()


def close_tab(tab_id: str, *, rerun: bool = True) -> None:
    _ensure_tabs()
    tabs = st.session_state.workspace_tabs
    index = next((i for i, tab in enumerate(tabs) if tab.get("id") == tab_id), None)
    if index is None or not tabs[index].get("closable"):
        return
    was_active = st.session_state.get("active_tab_id") == tab_id
    tabs.pop(index)
    if was_active:
        fallback = tabs[min(index, len(tabs) - 1)] if tabs else _default_tabs()[0]
        st.session_state.workspace_tabs = tabs or _default_tabs()
        activate_tab(fallback["id"], rerun=False)
    if rerun:
        st.rerun()


def close_active_stock_tab(*, rerun: bool = True) -> None:
    tab_id = str(st.session_state.get("active_tab_id") or "")
    tab = _tab_by_id(tab_id)
    if tab and tab.get("kind") == "stock":
        close_tab(tab_id, rerun=rerun)
        return
    st.session_state.selected_symbol = None
    if rerun:
        st.rerun()


def _navigation_changed() -> None:
    # A Streamlit widget callback already triggers its own rerun. Calling
    # st.rerun() inside the callback causes the warning seen in v0.98.2.
    open_page_tab(st.session_state.navigation_page_picker, rerun=False)


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


def render_navigation() -> None:
    active_page = normalize_page(st.session_state.get("active_page"))
    if st.session_state.get("navigation_page_picker") != active_page:
        st.session_state.navigation_page_picker = active_page

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


def render_workspace_tabs() -> None:
    """Render desktop-style workspace tabs above the active page.

    Sidebar navigation remains permanent. These tabs are the user's active
    workspace: pages they opened plus closeable stock reports.
    """
    _ensure_tabs()
    tabs = st.session_state.workspace_tabs
    active_id = str(st.session_state.get("active_tab_id") or "")

    st.markdown(
        """
        <style>
        div[data-testid="stHorizontalBlock"]:has(.momopro-workspace-marker) {
            gap: .25rem;
            align-items: center;
        }
        .momopro-workspace-caption {
            color: rgba(250,250,250,.58);
            font-size: .78rem;
            margin-bottom: .25rem;
        }
        </style>
        <div class="momopro-workspace-marker"></div>
        <div class="momopro-workspace-caption">WORKSPACE</div>
        """,
        unsafe_allow_html=True,
    )

    # Wrap tabs into compact rows so the workspace remains usable on laptops.
    for row_start in range(0, len(tabs), 6):
        row_tabs = tabs[row_start:row_start + 6]
        weights: list[float] = []
        for tab in row_tabs:
            weights.extend([4.0, 0.8] if tab.get("closable") else [4.0])
        columns = st.columns(weights, gap="small")
        column_index = 0
        for tab in row_tabs:
            label = str(tab.get("label") or tab.get("page") or "Tab")
            if tab.get("kind") == "page":
                label = f"{_LABEL_TO_ICON.get(normalize_page(tab.get('page')), '•')} {label}"
            else:
                label = f"📄 {label}"
            with columns[column_index]:
                if st.button(
                    label,
                    key=f"workspace_tab_{tab['id']}",
                    type="primary" if tab["id"] == active_id else "secondary",
                    use_container_width=True,
                ):
                    activate_tab(tab["id"])
            column_index += 1
            if tab.get("closable"):
                with columns[column_index]:
                    if st.button("×", key=f"close_workspace_tab_{tab['id']}", help=f"Close {tab.get('label')}"):
                        close_tab(tab["id"])
                column_index += 1
    st.divider()


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

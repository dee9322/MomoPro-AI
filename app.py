from uuid import uuid4

import pandas as pd
from position_sizing import calculate_position_size
import streamlit as st

from ai_commentary import (
    build_momo_engine_decision,
    generate_ai_decision,
)
from ai_research import generate_research_report
from ai_chat import answer_research_question
from ai_vision import analyze_chart_image
from comparison_research import detect_comparison_query, research_comparison
from alpaca_test import (
    test_alpaca_connection,
)
from scanner import run_scan
from massive_market_data import render_scanner_v2_setup
from scanner_runtime import (
    ensure_scan_started, job_state as scanner_job_state, load_latest_scan_results,
    latest_scan_is_fresh, scanner_status_text, local_manifest as scanner_local_manifest,
)
from confidence import calculate_integrated_confidence
from market_context import get_market_context
from relative_strength import get_relative_strength
from news_intelligence import (
    get_market_news,
    get_ticker_news,
    rank_news,
    summarize_news,
)
from sec_intelligence import get_recent_filings
from fda_intelligence import get_fda_enforcement
from smart_money import get_smart_money_intelligence
from news_ai import analyze_news
from trade_intelligence import get_trade_intelligence
from dashboard_engine import (
    UNIVERSE_OPTIONS, broker_status, filter_scan_universe, load_open_trades,
    market_index_rows, rank_scanner_candidates, recent_ai_recommendations,
    sector_rows, unread_watchlist_alerts,
)
from dashboard_brief import build_today_trading_plan

from watchlist_manager import (
    add_symbols, create_watchlist, delete_watchlist, get_symbols,
    get_watchlist_item, list_watchlists, remove_symbol, rename_watchlist,
    update_watchlist_item,
)
from watchlist_ai import build_morning_brief, refresh_item_from_scan, sync_ai_report_to_item
from watchlist_models import WatchlistItem, utc_now
from alert_engine import (
    clear_events, create_rule, delete_rule, evaluate_alerts, load_alerts,
    mark_event_read, set_rule_enabled,
)
from alert_rules import RULE_TYPES
from trade_journal import (
    add_exit, add_management_update, broker_import_status, create_trade, delete_trade, get_trade,
    import_webull_history, reopen_trade, trade_summary, update_trade,
)
from broker_import import preview_webull_csv
from trade_storage import load_broker_executions, load_broker_imports, load_broker_orders
from webull_sync import load_webull_snapshot, sync_webull, webull_connection_status
from trade_storage import load_trades, save_attachment
from performance_engine import (
    SOURCE_OPTIONS, calculate_summary, data_quality_report, decision_accuracy, equity_curve,
    filter_performance_frame, group_performance, monthly_performance, review_metrics,
    trade_timeline, trades_to_frame,
)
from performance_insights import build_performance_insights
from learning_engine import build_learning_report, evidence_level
from learning_insights import build_coaching
from learning_storage import (
    add_approved_rule, delete_rule as delete_learning_rule, load_learning_data,
    save_snapshot as save_learning_snapshot, set_rule_enabled as set_learning_rule_enabled,
)
from settings_engine import (
    get_account_context, get_effective_account_size, get_setting, get_settings, reset_settings, save_settings, settings_summary, update_section,
)
from canonical_analysis import build_canonical_analysis, planner_prefill
from analysis_storage import save_analysis, get_analysis, list_analyses
from chart_data import available_timeframes, latest_chart_snapshot, load_chart_bars
from chart_engine import build_live_chart
from trade_classification import classification_label
from historical_reconstruction import reconstruct_trade
from broker_order_intelligence import has_reliable_broker_time
from tradingview_bridge import (build_tradingview_payload, official_plan_packet, packet_diagnostics, payload_json, pine_input_block, tradingview_chart_url)
from auth_manager import require_auth, sign_out
from migration_manager import migrate_local_json_once
from workspace_storage import load_workspace, persist_session_workspace, save_workspace
from navigation_manager import (
    active_page_is, close_active_stock_tab, first_positive, initialize_navigation, navigate_to,
    normalize_symbol, open_stock_workspace, render_navigation, render_workspace_tabs,
    set_active_symbol, sync_symbol_widget,
)
from supabase_backend import is_supabase_configured
from cloud_storage import verify_cloud_access
from symbol_context import (
    analyze_symbol, attach_cached_metadata, available_cached_sectors, get_company_metadata,
    enrich_company_metadata_batch, normalize_stock_payload,
)
from automatic_loading import (
    initialize_automatic_loading, load_resource, force_refresh_resource,
    render_automatic_loading_worker,
    render_freshness, render_loading_skeleton, restore_saved_resource,
)
from app_utils import valid_value, money_text, percent_text, r_text, compact_number, reaction_text
from data_services import (
    secret as _secret, load_relative_strength, load_market_news, load_ticker_news,
    load_sec_filings, load_fda_records, load_smart_money,
    load_trade_intelligence, load_comparison_research,
)
from cache_policy import ttl_minutes as policy_ttl_minutes
from diagnostics import run_startup_checks
from logging_config import configure_logging, log_event
from startup_profiler import profile_step
from ui_components import render_health_monitor, render_error_diagnostic
from ui_design_system import (
    apply_design_system, build_reconstruction_coach, render_chart_thumbnail,
    render_coach_summary, render_empty_state,
)



APP_LOGGER = configure_logging()
STARTUP_TIMINGS = {}
log_event("startup", "Application import completed")

st.set_page_config(
    page_title="MomoPro AI",
    page_icon="📈",
    layout="wide",
)

apply_design_system()

# App-wide readability guardrails. Important labels, values, tabs, buttons,
# alerts, and table cells must wrap instead of being hidden behind ellipses.
st.markdown(
    """
    <style>
    [data-testid="stMetric"] {
        min-width: 0;
        overflow: visible;
    }
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] *,
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        word-break: break-word !important;
        line-height: 1.2 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: clamp(1.15rem, 2.2vw, 2rem) !important;
    }
    button, button *, [role="tab"], [role="tab"] *,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] * {
        text-overflow: clip !important;
    }
    [role="tab"] {
        white-space: normal !important;
        height: auto !important;
        min-height: 2.5rem;
        line-height: 1.2 !important;
    }
    button, button * {
        white-space: normal !important;
        overflow: visible !important;
        word-break: break-word !important;
    }
    [data-testid="stAlert"] p, [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] * {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        word-break: break-word !important;
    }
    [data-testid="stDataFrame"] {
        overflow-x: auto !important;
    }
    .momo-status-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 0.75rem;
        margin: 0.5rem 0 1rem 0;
    }
    .momo-status-card {
        border: 1px solid rgba(128,128,128,0.35);
        border-radius: 0.7rem;
        padding: 0.8rem 0.9rem;
        min-width: 0;
    }
    .momo-status-label {
        font-size: 0.78rem;
        opacity: 0.75;
        margin-bottom: 0.25rem;
        overflow-wrap: anywhere;
    }
    .momo-status-value {
        font-size: 1.05rem;
        font-weight: 700;
        line-height: 1.25;
        white-space: normal;
        overflow-wrap: anywhere;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with profile_step(STARTUP_TIMINGS, "authentication"):
    auth_state = require_auth()

if is_supabase_configured():
    cloud_ok, cloud_error = verify_cloud_access()
    if not cloud_ok:
        st.error("Your private MomoPro cloud workspace could not be restored safely.")
        st.info("Nothing has been reset or overwritten. Refresh the page to retry. If this continues, sign out and sign back in once.")
        if cloud_error:
            st.caption(f"Cloud restore detail: {cloud_error}")
        st.stop()
    migration_result = migrate_local_json_once()
else:
    migration_result = {"completed": False, "buckets": [], "skipped": []}

with st.sidebar:
    st.markdown("### MomoPro AI")
    st.caption(auth_state.email or "Local development mode")
    if is_supabase_configured():
        st.success("Cloud workspace connected")
        if migration_result.get("buckets"):
            st.caption(f"Imported {len(migration_result['buckets'])} local data areas into your private workspace.")
        if st.button("Sign out", width="stretch", key="momopro_sign_out"):
            sign_out()
            st.rerun()
    else:
        st.warning("Local fallback mode: add Supabase secrets before public release.")

    try:
        startup_checks = run_startup_checks(
            supabase_configured=is_supabase_configured(),
            secrets=list(st.secrets.keys()),
        )
    except Exception as exc:
        log_event("diagnostics", "Startup checks failed", level=30, error=str(exc))
        startup_checks = []
    render_health_monitor(startup_checks, STARTUP_TIMINGS)

st.title("📈 MomoPro AI")
st.subheader(
    "Your AI Swing Trading Partner"
)




initialize_automatic_loading()

if "momopro_workspace" not in st.session_state:
    st.session_state.momopro_workspace = load_workspace()

if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = st.session_state.momopro_workspace.get("selected_symbol")

initialize_navigation(st.session_state.momopro_workspace)

if "ai_commentary_cache" not in st.session_state:
    st.session_state.ai_commentary_cache = {}

if "market_context" not in st.session_state:
    st.session_state.market_context = None

if "news_ai_cache" not in st.session_state:
    st.session_state.news_ai_cache = {}

if "news_search_symbol" not in st.session_state:
    st.session_state.news_search_symbol = st.session_state.momopro_workspace.get("news_search_symbol", "")

if "smart_money_cache" not in st.session_state:
    st.session_state.smart_money_cache = {}

if "trade_intelligence_cache" not in st.session_state:
    st.session_state.trade_intelligence_cache = {}

if "canonical_analysis_cache" not in st.session_state:
    st.session_state.canonical_analysis_cache = {}

if "trade_plan_prefill" not in st.session_state:
    st.session_state.trade_plan_prefill = dict(st.session_state.momopro_workspace.get("trade_plan_prefill") or {})

if "ai_research_reports" not in st.session_state:
    st.session_state.ai_research_reports = {}

if "ai_research_evidence" not in st.session_state:
    st.session_state.ai_research_evidence = {}

if "ai_chat_history" not in st.session_state:
    st.session_state.ai_chat_history = {}

if "global_ai_history" not in st.session_state:
    st.session_state.global_ai_history = []

if "global_ai_last_meta" not in st.session_state:
    st.session_state.global_ai_last_meta = {}

if "momopro_settings" not in st.session_state:
    st.session_state.momopro_settings = get_settings()

# Restore the canonical saved Webull account snapshot during application initialization.
# refresh=False prevents a page render from depending on a live broker request.
st.session_state.momopro_account_context = get_account_context(
    st.session_state.momopro_settings, refresh=False
)

if "dashboard_universe" not in st.session_state:
    st.session_state.dashboard_universe = get_setting(
        "dashboard.default_universe", "Entire Market", st.session_state.momopro_settings
    )

if "dashboard_headlines" not in st.session_state:
    st.session_state.dashboard_headlines = []

if "journal_prefill" not in st.session_state:
    st.session_state.journal_prefill = dict(st.session_state.momopro_workspace.get("journal_prefill") or {})

if "live_chart_symbol" not in st.session_state:
    # The restored shared ticker is authoritative. A stale saved chart default
    # (commonly SPY) must never override the symbol restored from the URL/cloud.
    st.session_state.live_chart_symbol = str(
        st.session_state.get("selected_symbol")
        or st.session_state.momopro_workspace.get("chart_symbol")
        or "SPY"
    ).upper().strip()
if "live_chart_timeframe" not in st.session_state:
    st.session_state.live_chart_timeframe = str(
        st.session_state.momopro_workspace.get("chart_timeframe") or "1D"
    )
if "live_chart_candles" not in st.session_state:
    st.session_state.live_chart_candles = int(
        st.session_state.momopro_workspace.get("chart_candles") or 300
    )
if "live_chart_overlays" not in st.session_state:
    st.session_state.live_chart_overlays = list(
        st.session_state.momopro_workspace.get("chart_overlays") or []
    )

render_navigation()
render_workspace_tabs()
active_page = st.session_state.active_page


def _data_cache_minutes(name: str, default: int) -> int:
    policy_default = policy_ttl_minutes(name, default)
    try:
        return int(get_setting(f"data.{name}_cache_minutes", policy_default, st.session_state.momopro_settings) or policy_default)
    except Exception as exc:
        log_event("cache", "Falling back to central cache policy", level=30, resource=name, error=str(exc))
        return policy_default


def _load_market_context_for_page():
    return get_market_context(st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_SECRET_KEY"])


def _load_ranked_market_news_for_page():
    return rank_news(load_market_news())


def _autoload_active_page():
    """Queue only the active page's resources; the fragment worker loads them after paint."""
    page = str(active_page or "")
    market_ttl = _data_cache_minutes("market", 15)
    news_ttl = _data_cache_minutes("news", 15)
    scanner_ttl = _data_cache_minutes("scanner", 30)

    if page in {"Dashboard", "Market Context", "AI Analysis", "Watchlist", "Journal"}:
        load_resource(
            "market_context", "market_context", _load_market_context_for_page,
            ttl_minutes=market_ttl, loading_label="Loading current market context",
        )

    # Scanner v2 deliberately does NOT use the generic automatic-loading queue.
    # Whole-market work runs in scanner_runtime's isolated worker so a Scanner
    # refresh can never hold Dashboard, News, Watchlist or navigation hostage.
    if page in {"Dashboard", "Scanner"} and st.session_state.get("scan_results") is None:
        restored_scan = load_latest_scan_results()
        if restored_scan is not None and not restored_scan.empty:
            st.session_state.scan_results = restored_scan

    if page in {"Dashboard", "News"}:
        load_resource(
            "market_news", "dashboard_headlines", _load_ranked_market_news_for_page,
            ttl_minutes=news_ttl, loading_label="Loading current market news",
        )


_autoload_active_page()


# -----------------------------
# Dashboard — Morning Command Center
# -----------------------------
if active_page_is("Dashboard"):
    st.header("Morning Command Center")
    st.caption("Market health, leadership, opportunities, alerts, open trades, and today’s plan in one place.")
    render_freshness("market_context", ttl_minutes=_data_cache_minutes("market", 15), label="Market")
    render_freshness("market_news", ttl_minutes=_data_cache_minutes("news", 15), label="News")
    st.caption(f"Scanner: {scanner_status_text()}")
    if not st.session_state.get("market_context") or not st.session_state.get("dashboard_headlines") or st.session_state.get("scan_results") is None:
        render_loading_skeleton("market_context", rows=2, label="Preparing Dashboard market data")
        render_loading_skeleton("market_news", rows=2, label="Preparing Dashboard news")
        render_loading_skeleton("market_scan", rows=2, label="Preparing Dashboard opportunities")

    control_left, control_mid, control_right = st.columns([2, 1, 1])
    with control_left:
        dashboard_universe = st.selectbox(
            "Universe",
            UNIVERSE_OPTIONS,
            index=UNIVERSE_OPTIONS.index(st.session_state.dashboard_universe),
            key="dashboard_universe_selector",
        )
        st.session_state.dashboard_universe = dashboard_universe
    with control_mid:
        refresh_market = st.button("Refresh Market", width="stretch", key="dashboard_refresh_market")
    with control_right:
        refresh_news = st.button("Refresh News", width="stretch", key="dashboard_refresh_news")

    if refresh_market:
        with st.spinner("Refreshing the market command center..."):
            try:
                st.session_state.market_context = force_refresh_resource(
                    "market_context", "market_context", _load_market_context_for_page,
                    ttl_minutes=_data_cache_minutes("market", 15), loading_label="Refreshing market context",
                )
                st.info("Market Context refresh started automatically.")
            except Exception as error:
                st.error(f"Market Context refresh failed: {error}")

    if refresh_news:
        load_market_news.clear()
        try:
            st.session_state.dashboard_headlines = force_refresh_resource(
                "market_news", "dashboard_headlines", _load_ranked_market_news_for_page,
                ttl_minutes=_data_cache_minutes("news", 15), loading_label="Refreshing market news",
            )
            st.info("Market headlines refresh started automatically.")
        except Exception as error:
            st.warning(f"Market headlines are temporarily unavailable: {error}")

    dashboard_market = st.session_state.market_context
    # Do not silently run a live news request during Dashboard rendering. Saved
    # headlines appear immediately; Refresh News is the deliberate live action.
    dashboard_news = st.session_state.dashboard_headlines[:10]

    filtered_scan, universe_note = filter_scan_universe(
        st.session_state.scan_results,
        dashboard_universe,
        st.session_state.get("active_watchlist"),
    )
    candidates = rank_scanner_candidates(filtered_scan, limit=10)
    alerts = unread_watchlist_alerts(limit=10)
    open_trades = load_open_trades(limit=10)
    ai_recommendations = recent_ai_recommendations(st.session_state.ai_research_reports, limit=8)

    market_score = dashboard_market.get("market_score") if dashboard_market else None
    market_trend = dashboard_market.get("market_trend", "—") if dashboard_market else "—"
    risk_environment = dashboard_market.get("risk_environment", "—") if dashboard_market else "—"
    breadth = (dashboard_market or {}).get("breadth", {})
    sentiment = (dashboard_market or {}).get("sentiment", {})
    sectors = (dashboard_market or {}).get("sectors", {})
    leaders = sectors.get("leaders") or []
    top_sector = leaders[0] if leaders else {}

    metrics = st.columns(7)
    metrics[0].metric("Market Health", market_score if market_score is not None else "—")
    metrics[1].metric("Market Trend", market_trend)
    metrics[2].metric("Risk", risk_environment)
    metrics[3].metric("Breadth", breadth.get("breadth_status", "—"), f"{breadth.get('breadth_score')}/100" if breadth.get("breadth_score") is not None else None)
    metrics[4].metric("Fear & Greed", sentiment.get("fear_greed_label", "—"), f"{sentiment.get('fear_greed_score')}/100" if sentiment.get("fear_greed_score") is not None else None)
    metrics[5].metric("Top Sector", top_sector.get("sector", "—"), f"{top_sector.get('score')}/100" if top_sector.get("score") is not None else None)
    metrics[6].metric("Unread Alerts", len(alerts))

    plan = build_today_trading_plan(
        market_context=dashboard_market,
        candidates=candidates,
        alert_count=len(alerts),
        open_trade_count=len(open_trades),
        headline_count=len(dashboard_news),
    )
    st.subheader("Today’s Trading Plan")
    st.info(f"**{plan['headline']}**\n\n{plan['plan']}")
    st.caption(f"Suggested risk posture: {plan['risk_posture']}")

    st.divider()
    st.subheader("Market Health & Index Leadership")
    index_rows = market_index_rows(dashboard_market)
    if index_rows:
        st.dataframe(pd.DataFrame(index_rows), width="stretch", hide_index=True)
    else:
        st.caption("Market context loads automatically; use Refresh Market only to force an immediate update.")

    breadth_col, sector_col = st.columns(2)
    with breadth_col:
        st.markdown("#### Breadth & Sentiment")
        if dashboard_market:
            breadth_metrics = st.columns(3)
            breadth_metrics[0].metric("Above EMA21", percent_text(breadth.get("above_ema21_pct")))
            breadth_metrics[1].metric("Above EMA50", percent_text(breadth.get("above_ema50_pct")))
            breadth_metrics[2].metric("Above EMA200", percent_text(breadth.get("above_ema200_pct")))
            st.write(breadth.get("summary", "Breadth summary unavailable."))
            st.write(f"**Risk appetite:** {sentiment.get('risk_appetite', '—')}")
            if sentiment.get("warning"):
                st.warning(sentiment.get("warning"))
        else:
            st.caption("Market breadth is not loaded.")
    with sector_col:
        st.markdown("#### Sector Leaders & Laggards")
        sector_leaders, sector_laggards = sector_rows(dashboard_market)
        if sector_leaders or sector_laggards:
            sector_table = []
            for item in sector_leaders:
                sector_table.append({"Group": "Leader", "Sector": item.get("sector"), "Score": item.get("score"), "Trend": item.get("trend"), "Rotation": item.get("rotation")})
            for item in sector_laggards:
                sector_table.append({"Group": "Laggard", "Sector": item.get("sector"), "Score": item.get("score"), "Trend": item.get("trend"), "Rotation": item.get("rotation")})
            st.dataframe(pd.DataFrame(sector_table), width="stretch", hide_index=True)
        else:
            st.caption("Sector leadership is not loaded.")

    st.divider()
    left, right = st.columns([1.25, 1])
    with left:
        st.subheader(f"Top Scanner Candidates — {dashboard_universe}")
        if universe_note:
            st.caption(universe_note)
        if candidates:
            candidate_df = pd.DataFrame(candidates)
            st.dataframe(candidate_df, width="stretch", hide_index=True)
            selected_dashboard_symbol = st.selectbox(
                "Load candidate into Stock Report",
                [item["Symbol"] for item in candidates],
                key="dashboard_candidate_selector",
            )
            if st.button("Open Selected Candidate", key="dashboard_open_candidate"):
                st.session_state.selected_symbol = selected_dashboard_symbol
                st.success(f"{selected_dashboard_symbol} is loaded. Open the Scanner tab to view its Stock Report.")
        else:
            st.caption("No candidates match this universe yet.")

    with right:
        st.subheader("Watchlist Alerts")
        if alerts:
            for event in alerts[:6]:
                symbol = event.get("symbol", "—")
                message = event.get("message") or event.get("reason") or event.get("rule_name") or "Alert triggered"
                st.markdown(f"**{symbol}** — {message}")
                st.caption(event.get("triggered_at") or event.get("created_at") or "")
        else:
            st.caption("No unread watchlist alerts.")

        st.markdown("#### Open Trades")
        if open_trades:
            st.dataframe(pd.DataFrame(open_trades), width="stretch", hide_index=True)
        else:
            st.caption("No open journal trades yet.")

        st.markdown("#### Webull Import Status")
        webull_status = broker_status()
        if webull_status.get("connected"):
            status_cols = st.columns(3)
            status_cols[0].metric("Executions", webull_status.get("executions", 0))
            status_cols[1].metric("Imports", webull_status.get("imports", 0))
            status_cols[2].metric("Unmatched", webull_status.get("unmatched", 0))
            st.caption(f"Last import: {webull_status.get('last_import') or '—'} · {webull_status.get('last_file') or '—'}")
        else:
            st.caption("Upload a Webull CSV in Journal → Broker Import & Reconcile to backfill history.")

    st.divider()
    news_col, ai_col = st.columns(2)
    with news_col:
        st.subheader("Macro & Breaking Market News")
        if dashboard_news:
            for item in dashboard_news[:7]:
                headline = item.get("headline", "Untitled headline")
                if item.get("url"):
                    st.markdown(f"**[{headline}]({item.get('url')})**")
                else:
                    st.markdown(f"**{headline}**")
                st.caption(f"{item.get('category', 'Market')} · {item.get('impact', '—')} impact · {item.get('sentiment', 'Neutral')}")
        else:
            st.caption("No recent market headlines were returned.")
    with ai_col:
        st.subheader("Recent Independent AI Recommendations")
        if ai_recommendations:
            ai_table = pd.DataFrame(ai_recommendations).drop(columns=["Summary"], errors="ignore")
            if "AI Confidence" in ai_table.columns:
                ai_table["AI Confidence"] = ai_table["AI Confidence"].map(lambda value: "—" if value in (None, "", "—") or pd.isna(value) else f"{float(value):.0f}%")
            st.dataframe(ai_table, width="stretch", hide_index=True)
            with st.expander("Latest AI summaries"):
                for item in ai_recommendations[:5]:
                    st.markdown(f"**{item['Symbol']} — {item['Action']} ({item.get('AI Confidence', '—')}%)**")
                    st.write(item.get("Summary") or "No executive summary stored.")
        else:
            st.caption("Independent AI recommendations will appear after Full Independent AI Research is generated.")

    st.divider()
    with st.expander("Connection Test"):
        if st.button("Test Alpaca Connection", key="test_alpaca"):
            success, status, buying_power = test_alpaca_connection()
            if success:
                st.success("Alpaca connected successfully.")
                st.write(f"Account status: {status}")
                st.write(f"Buying power: ${buying_power}")
            else:
                st.error("Alpaca connection failed.")
                st.write(status)


# -----------------------------
# Market Context
# -----------------------------
if active_page_is("Market Context"):
    st.header("Market Context")
    render_freshness("market_context", ttl_minutes=_data_cache_minutes("market", 15), label="Market context")
    st.caption(
        "The latest broad-market assessment loads automatically when this tab opens. "
        "Use Refresh only when you want to force a new request."
    )

    if st.button(
        "Refresh Market Context",
        key="refresh_market_context",
    ):
        try:
            with st.spinner("Analyzing the broad market and breadth..."):
                st.session_state.market_context = force_refresh_resource(
                    "market_context", "market_context", _load_market_context_for_page,
                    ttl_minutes=_data_cache_minutes("market", 15), loading_label="Refreshing market context",
                )
        except Exception as error:
            st.error(f"Market context could not be loaded: {error}")

    market = st.session_state.market_context
    if not market:
        render_loading_skeleton("market_context", rows=4, label="Analyzing broad-market conditions")

    if market:
        top = st.columns(5)
        top[0].metric("Market Score", market.get("market_score", "—"))
        top[1].metric("Market Trend", market.get("market_trend", "—"))
        top[2].metric("Risk Environment", market.get("risk_environment", "—"))
        breadth = market.get("breadth", {})
        top[3].metric(
            "Breadth",
            breadth.get("breadth_status", "—"),
            (
                f'{breadth.get("breadth_score")}/100'
                if breadth.get("breadth_score") is not None
                else None
            ),
        )
        sentiment = market.get("sentiment", {})
        top[4].metric(
            "Sentiment",
            sentiment.get("fear_greed_label", "—"),
            (
                f'{sentiment.get("fear_greed_score")}/100'
                if sentiment.get("fear_greed_score") is not None
                else None
            ),
        )

        st.info(market.get("summary", "No market summary available."))

        st.subheader("Major Indexes")
        rows = []
        for symbol in ("SPY", "QQQ", "IWM", "DIA", "VIXY"):
            item = market.get("indexes", {}).get(symbol, {})
            rows.append(
                {
                    "Symbol": symbol,
                    "Name": item.get("label"),
                    "Trend": item.get("trend"),
                    "Score": item.get("score"),
                    "Close": item.get("close"),
                    "RSI": item.get("rsi14"),
                    "Above EMA21": item.get("above_ema21"),
                    "Above EMA50": item.get("above_ema50"),
                    "Above EMA200": item.get("above_ema200"),
                    "5D %": item.get("return_5d_pct"),
                    "20D %": item.get("return_20d_pct"),
                    "60D %": item.get("return_60d_pct"),
                    "20D vs SPY": item.get("relative_20d_vs_spy"),
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(f'Volatility source: {market.get("vix_source", "Unavailable")}')

        st.divider()
        st.subheader("Market Breadth")
        if breadth.get("status") == "Available":
            b1 = st.columns(4)
            b1[0].metric("Advancing", breadth.get("advancing", 0))
            b1[1].metric("Declining", breadth.get("declining", 0))
            b1[2].metric(
                "Advance / Decline",
                breadth.get("advance_decline_ratio", "—"),
            )
            b1[3].metric("Stocks Analyzed", breadth.get("stocks_analyzed", 0))

            b2 = st.columns(3)
            b2[0].metric("Above EMA21", percent_text(breadth.get("above_ema21_pct")))
            b2[1].metric("Above EMA50", percent_text(breadth.get("above_ema50_pct")))
            b2[2].metric("Above EMA200", percent_text(breadth.get("above_ema200_pct")))

            b3 = st.columns(3)
            b3[0].metric("New 20-Day Highs", breadth.get("new_20_day_highs", 0))
            b3[1].metric("New 20-Day Lows", breadth.get("new_20_day_lows", 0))
            b3[2].metric("High / Low Ratio", breadth.get("high_low_ratio", "—"))
            st.write(breadth.get("summary", ""))
            st.caption(breadth.get("universe_label", ""))
        else:
            st.warning(breadth.get("summary", "Breadth is unavailable."))

        st.divider()
        st.subheader("Market Sentiment")
        sentiment = market.get("sentiment", {})

        if sentiment.get("status") == "Available":
            s1 = st.columns(4)
            s1[0].metric(
                "Momo Fear & Greed",
                sentiment.get("fear_greed_label", "—"),
                (
                    f'{sentiment.get("fear_greed_score")}/100'
                    if sentiment.get("fear_greed_score") is not None
                    else None
                ),
            )
            s1[1].metric(
                "Total Put / Call",
                sentiment.get("total_put_call_ratio", "—"),
            )
            s1[2].metric(
                "Equity Put / Call",
                sentiment.get("equity_put_call_ratio", "—"),
            )
            s1[3].metric(
                "Risk Appetite",
                sentiment.get("risk_appetite", "—"),
            )

            st.write(sentiment.get("summary", ""))

            if sentiment.get("warning"):
                st.warning(sentiment.get("warning"))

            st.caption(
                "Fear & Greed is MomoPro's transparent composite using broad "
                "trend, breadth, volatility, and official Cboe put/call data. "
                f'Source: {sentiment.get("source", "Unavailable")}.'
            )
        else:
            st.warning(sentiment.get("summary", "Sentiment is unavailable."))

        st.divider()
        st.subheader("Sector Strength & Rotation")
        sectors = market.get("sectors", {})

        if sectors.get("status") == "Available":
            sec_top = st.columns(4)
            sec_top[0].metric("Sector Score", sectors.get("sector_score", "—"))
            sec_top[1].metric("Rotation", sectors.get("rotation_regime", "—"))
            sec_top[2].metric(
                "Risk-On Average",
                sectors.get("risk_on_average", "—"),
            )
            sec_top[3].metric(
                "Defensive Average",
                sectors.get("defensive_average", "—"),
            )

            st.write(sectors.get("summary", ""))

            sector_rows = []
            for item in sectors.get("rankings", []):
                sector_rows.append(
                    {
                        "Rank": len(sector_rows) + 1,
                        "Sector": item.get("sector"),
                        "ETF": item.get("symbol"),
                        "Score": item.get("score"),
                        "Trend": item.get("trend"),
                        "Rotation": item.get("rotation"),
                        "5D %": item.get("return_5d_pct"),
                        "20D %": item.get("return_20d_pct"),
                        "60D %": item.get("return_60d_pct"),
                        "20D vs SPY": item.get("relative_20d_vs_spy"),
                        "RSI": item.get("rsi14"),
                    }
                )

            st.dataframe(
                pd.DataFrame(sector_rows),
                width="stretch",
                hide_index=True,
            )

            leader_col, laggard_col = st.columns(2)

            with leader_col:
                st.markdown("#### Leading Sectors")
                for item in sectors.get("leaders", []):
                    st.write(
                        f'• {item.get("sector")} ({item.get("symbol")}) — '
                        f'{item.get("score")}/100 · {item.get("rotation")}'
                    )

            with laggard_col:
                st.markdown("#### Lagging Sectors")
                for item in sectors.get("laggards", []):
                    st.write(
                        f'• {item.get("sector")} ({item.get("symbol")}) — '
                        f'{item.get("score")}/100 · {item.get("rotation")}'
                    )
        else:
            st.warning(sectors.get("summary", "Sector strength is unavailable."))

        st.divider()
        st.subheader("Market Relative Strength")
        st.caption(
            "This section compares major indexes and sectors against SPY. "
            "Stock-specific relative strength remains inside each Stock Report."
        )

        index_rs_rows = []
        for symbol in ("SPY", "QQQ", "IWM", "DIA"):
            item = market.get("indexes", {}).get(symbol, {})
            index_rs_rows.append(
                {
                    "Index": item.get("label", symbol),
                    "ETF": symbol,
                    "Trend": item.get("trend"),
                    "5D %": item.get("return_5d_pct"),
                    "20D %": item.get("return_20d_pct"),
                    "60D %": item.get("return_60d_pct"),
                    "5D vs SPY": item.get("relative_5d_vs_spy"),
                    "20D vs SPY": item.get("relative_20d_vs_spy"),
                    "60D vs SPY": item.get("relative_60d_vs_spy"),
                }
            )

        st.markdown("#### Index Leadership")
        st.dataframe(
            pd.DataFrame(index_rs_rows),
            width="stretch",
            hide_index=True,
        )

        if sectors.get("status") == "Available":
            st.markdown("#### Sector Leadership vs SPY")
            rs_rows = []
            for item in sectors.get("rankings", []):
                rs_rows.append(
                    {
                        "Rank": len(rs_rows) + 1,
                        "Sector": item.get("sector"),
                        "ETF": item.get("symbol"),
                        "5D vs SPY": item.get("relative_5d_vs_spy"),
                        "20D vs SPY": item.get("relative_20d_vs_spy"),
                        "60D vs SPY": item.get("relative_60d_vs_spy"),
                        "Rotation": item.get("rotation"),
                    }
                )

            st.dataframe(
                pd.DataFrame(rs_rows),
                width="stretch",
                hide_index=True,
            )
            st.caption(
                "Positive values indicate outperformance versus SPY; negative "
                "values indicate lagging performance over the same period."
            )
        else:
            st.caption("Sector relative-strength leadership is unavailable.")
    else:
        st.info("Market Context is loading automatically. Use Refresh only to force a new request.")


# -----------------------------
# Scanner
# -----------------------------
if active_page_is("Scanner"):
    st.header("Scanner")
    st.caption(f"Scanner: {scanner_status_text()}")

    st.caption(
        "Latest saved candidates appear immediately. If the scan is stale, Scanner refreshes automatically; Run New Market Scan is only a force-refresh control."
    )

    render_scanner_v2_setup()

    # Restore the last persisted candidate list immediately, even while the
    # Scanner v2 foundation is still building. This prevents a blank Scanner
    # after a Streamlit sleep/redeploy.
    current_scan = st.session_state.get("scan_results")
    if current_scan is None or (hasattr(current_scan, "empty") and current_scan.empty):
        persisted_scan = load_latest_scan_results()
        if persisted_scan is not None and not persisted_scan.empty:
            st.session_state.scan_results = persisted_scan

    # Normal Scanner behavior is automatic: restore saved results immediately,
    # then refresh in the isolated scanner worker only when stale.
    scanner_manifest = scanner_local_manifest()
    if scanner_manifest.get("ready"):
        ensure_scan_started(force=False)

    if st.button(
        "Run New Market Scan",
        key="run_market_scan",
        type="primary",
        width="stretch",
    ):
        ensure_scan_started(force=True)
        st.session_state.selected_symbol = None
        st.info("Force refresh started in the Scanner v2 worker. You can leave this page while it runs.")

    # Pick up a finished background result without blocking page rendering.
    scan_state = scanner_job_state("scan")
    if scan_state.get("done") and not scan_state.get("running"):
        newest_scan = load_latest_scan_results()
        if newest_scan is not None and not newest_scan.empty:
            st.session_state.scan_results = newest_scan
    if scan_state.get("running"):
        progress_value = scan_state.get("progress")
        if isinstance(progress_value, (int, float)):
            st.progress(max(0.0, min(1.0, float(progress_value))))
        st.caption(str(scan_state.get("stage") or "Refreshing current candidates in background"))

    df = st.session_state.scan_results
    if df is None or (hasattr(df, "empty") and df.empty):
        if not scanner_manifest.get("ready"):
            st.info("Scanner v2 is building its one-time market-history foundation in the background. The rest of MomoPro remains fully usable.")
        else:
            st.info("Scanner v2 is preparing the first current candidate list in the background.")

    if df is not None and not df.empty:
        # v0.98.4: enrich the current result set, not only symbols that happened
        # to be opened previously. Provider failures are isolated per symbol.
        enrich_company_metadata_batch(
            df["Symbol"].astype(str).tolist(),
            fmp_api_key=_secret("FMP_API_KEY"),
            alpha_vantage_api_key=_secret("ALPHA_VANTAGE_API_KEY"),
            max_workers=3,
        )
        df = attach_cached_metadata(df)
        # Market cap can be safely estimated when reported shares outstanding
        # exist and the scanner already has the current close.
        if "Market Cap" in df.columns and "Shares Outstanding" in df.columns and "Close" in df.columns:
            missing_cap = df["Market Cap"].isna() & df["Shares Outstanding"].notna()
            df.loc[missing_cap, "Market Cap"] = (
                pd.to_numeric(df.loc[missing_cap, "Close"], errors="coerce")
                * pd.to_numeric(df.loc[missing_cap, "Shares Outstanding"], errors="coerce")
            )
        st.session_state.scan_results = df
        sector_options = ["All Sectors"] + available_cached_sectors()
        selected_sector = st.selectbox(
            "Sector filter", sector_options, key="scanner_sector_filter",
            help="Sector choices appear as company metadata is cached."
        )
        if selected_sector != "All Sectors" and "Sector" in df.columns:
            df = df[df["Sector"].fillna("") == selected_sector].copy()
        matched_count = len(df)
        universe_count = int(pd.to_numeric(df.get("__Universe Count"), errors="coerce").dropna().max()) if "__Universe Count" in df.columns and not pd.to_numeric(df.get("__Universe Count"), errors="coerce").dropna().empty else None
        prescreened_count = int(pd.to_numeric(df.get("__Prescreened Count"), errors="coerce").dropna().max()) if "__Prescreened Count" in df.columns and not pd.to_numeric(df.get("__Prescreened Count"), errors="coerce").dropna().empty else 0
        eligible_count = int(pd.to_numeric(df.get("__Prescreen Eligible Count"), errors="coerce").dropna().max()) if "__Prescreen Eligible Count" in df.columns and not pd.to_numeric(df.get("__Prescreen Eligible Count"), errors="coerce").dropna().empty else prescreened_count
        bars_count = int(pd.to_numeric(df.get("__Prescreen Bars Count"), errors="coerce").dropna().max()) if "__Prescreen Bars Count" in df.columns and not pd.to_numeric(df.get("__Prescreen Bars Count"), errors="coerce").dropna().empty else None
        scope_text = f" after full analysis of {prescreened_count:,} strategy-ranked symbols"
        if universe_count:
            scope_text += f" selected from {universe_count:,} eligible U.S. equities"
        st.success(
            f"Scan complete: {matched_count} candidates matched the strategy filters{scope_text}."
        )
        st.caption(
            "MomoPro now uses a strategy-aware pre-rank instead of a rigid activity-only gate. "
            f"{eligible_count:,} symbols passed price/history eligibility"
            + (f" from {bars_count:,} symbols with usable pre-screen data" if bars_count else "")
            + f", and the strongest {prescreened_count:,} received the complete indicator and setup analysis. "
            "Lower-volume stocks are ranked with a liquidity penalty rather than being discarded before the real engine sees them."
        )

        st.caption(
            "Click a row to open its "
            "Stock Report."
        )

        hidden_columns = {
            "__Universe Count": None,
            "__Prescreened Count": None,
            "__Prescreen Eligible Count": None,
            "__Prescreen Bars Count": None,
            "__Prescreen Strict Count": None,
            "__Prescreen Standard Count": None,
            "__Prescreen Expanded Count": None,
            "__Prescreen Request Failures": None,
            "__Usable History Count": None,
            "Momo Confidence": None,
            "Confidence Rating": None,
            "Trend Confidence": None,
            "Location Confidence": None,
            "Momentum Confidence": None,
            "Volume Confidence": None,
            "Opportunity Confidence": None,
            "Risk Confidence": None,
            "Structure Confidence": None,
            "EMA21": None,
            "EMA50": None,
            "EMA200": None,
            "RSI": None,
            "MACD": None,
            "MACD Signal": None,
            "MACD Histogram": None,

            "Support 1": None,
            "Support 2": None,
            "Support 3": None,

            "Resistance 1": None,
            "Resistance 2": None,
            "Resistance 3": None,

            "Support 1 Quality": None,
            "Support 2 Quality": None,
            "Support 3 Quality": None,

            "Resistance 1 Quality": None,
            "Resistance 2 Quality": None,
            "Resistance 3 Quality": None,

            "Support 1 Touches": None,
            "Support 2 Touches": None,
            "Support 3 Touches": None,

            "Resistance 1 Touches": None,
            "Resistance 2 Touches": None,
            "Resistance 3 Touches": None,

            "Reference Entry": None,
            "Risk Reference": None,
            "Reward Reference": None,
            "Risk Per Share": None,
            "Reward Per Share": None,
            "Risk Reward": None,
            "Risk Reward Status": None,

            "T1": None,
            "T1 Upside %": None,
            "T1 R": None,

            "T2": None,
            "T2 Upside %": None,
            "T2 R": None,

            "T3": None,
            "T3 Upside %": None,
            "T3 R": None,
        }

        table_event = st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="scanner_table",
            column_config=hidden_columns,
        )

        selected_rows = (
            table_event.selection.rows
        )

        if selected_rows:
            selected_index = (
                selected_rows[0]
            )

            selected_row = df.iloc[
                selected_index
            ]

            open_stock_workspace(selected_row["Symbol"], rerun=False)

        selected_symbol = (
            st.session_state
            .selected_symbol
        )

        if selected_symbol:
            matching_rows = df[df["Symbol"] == selected_symbol] if "Symbol" in df.columns else pd.DataFrame()
            selected_stock = matching_rows.iloc[0].to_dict() if not matching_rows.empty else None

            # A direct ticker search must build the same full report even when the
            # symbol is absent from today's scan. The scanner is discovery only.
            if selected_stock is None:
                direct_cache = st.session_state.setdefault("direct_symbol_analysis_cache", {})
                selected_stock = direct_cache.get(selected_symbol)
                if selected_stock is None:
                    with st.spinner(f"Building the full {selected_symbol} workspace..."):
                        try:
                            selected_stock = analyze_symbol(
                                st.secrets["ALPACA_API_KEY"],
                                st.secrets["ALPACA_SECRET_KEY"],
                                selected_symbol,
                            )
                            direct_cache[selected_symbol] = selected_stock
                        except Exception as error:
                            st.error(f"Could not build the {selected_symbol} Stock Workspace: {error}")
                            selected_stock = None

            if selected_stock is not None:
                metadata = get_company_metadata(
                    selected_symbol,
                    fmp_api_key=_secret("FMP_API_KEY"),
                    alpha_vantage_api_key=_secret("ALPHA_VANTAGE_API_KEY"),
                )
                selected_stock.update({
                    "Company": metadata.get("company"),
                    "Sector": metadata.get("sector"),
                    "Industry": metadata.get("industry"),
                    "Exchange": metadata.get("exchange"),
                    "Country": metadata.get("country"),
                    "Market Cap": metadata.get("market_cap"),
                    "Float": metadata.get("float_shares"),
                    "Shares Outstanding": metadata.get("shares_outstanding"),
                })

            if selected_stock is None:
                st.stop()

            st.divider()

            (
                header_left,
                header_right,
            ) = st.columns([4, 1])

            with header_left:
                st.header(
                    f"{selected_symbol} "
                    "Stock Report"
                )

                st.caption(
                    "MomoPro AI structural "
                    "swing-trade analysis."
                )
                identity_parts = [
                    selected_stock.get("Company"), selected_stock.get("Sector"),
                    selected_stock.get("Industry"), selected_stock.get("Exchange"),
                ]
                identity_text = " · ".join(str(item) for item in identity_parts if item)
                if identity_text:
                    st.caption(identity_text)

            with header_right:
                if st.button(
                    "Close Report",
                    key=(
                        "close_stock_report"
                    ),
                ):
                    close_active_stock_tab()

            metric_columns = st.columns(6)

            metric_columns[0].metric(
                "Grade",
                selected_stock.get(
                    "Grade",
                    "—",
                ),
            )

            metric_columns[1].metric(
                "Momo Score",
                selected_stock.get(
                    "Momo Score",
                    "—",
                ),
            )

            metric_columns[2].metric(
                "Dee Fit",
                selected_stock.get(
                    "Dee Fit",
                    "—",
                ),
            )

            metric_columns[3].metric(
                "Technical Score",
                selected_stock.get(
                    "Score",
                    "—",
                ),
            )

            metric_columns[4].metric(
                "Momo Confidence",
                percent_text(
                    selected_stock.get(
                        "Momo Confidence"
                    )
                ),
                selected_stock.get(
                    "Confidence Rating",
                    "—",
                ),
            )

            metric_columns[5].metric(
                "Close",
                money_text(
                    selected_stock.get(
                        "Close"
                    )
                ),
            )

            st.subheader("Setup")

            st.write(
                selected_stock.get(
                    "Setup",
                    "Not classified",
                )
            )

            st.subheader(
                "Current Scanner Read"
            )

            st.write(
                selected_stock.get(
                    "Reasons",
                    "No reasons available.",
                )
            )

            detail_columns = st.columns(3)

            detail_columns[0].metric(
                "ATR %",
                selected_stock.get(
                    "ATR %",
                    "—",
                ),
            )

            detail_columns[1].metric(
                "RVOL",
                selected_stock.get(
                    "RVOL",
                    "—",
                ),
            )

            detail_columns[2].metric(
                "Distance From EMA21",
                percent_text(
                    selected_stock.get(
                        "Distance EMA21 %"
                    )
                ),
            )

            # -------------------------
            # Market Backdrop
            # -------------------------
            st.divider()
            st.subheader("Market Backdrop")
            report_market = st.session_state.market_context
            if report_market:
                report_breadth = report_market.get("breadth", {})
                report_sentiment = report_market.get("sentiment", {})
                report_sectors = report_market.get("sectors", {})
                top_sector = (report_sectors.get("leaders") or [{}])[0]
                mc = st.columns(6)
                mc[0].metric("Market", report_market.get("market_trend", "—"))
                mc[1].metric("Risk", report_market.get("risk_environment", "—"))
                mc[2].metric("Market Score", report_market.get("market_score", "—"))
                mc[3].metric("Breadth", report_breadth.get("breadth_status", "—"))
                mc[4].metric("Sentiment", report_sentiment.get("fear_greed_label", "—"))
                mc[5].metric(
                    "Leading Sector",
                    top_sector.get("sector", "—"),
                    (
                        f'{top_sector.get("score")}/100'
                        if top_sector.get("score") is not None
                        else None
                    ),
                )
                st.caption(report_market.get("summary", ""))
                st.info(
                    "Open the Market Context tab for the full index, breadth, "
                    "sentiment, and sector-rotation breakdown."
                )
            else:
                st.caption("Market Context has not been loaded for this session.")

            # -------------------------
            # Relative Strength
            # -------------------------
            st.divider()
            st.subheader("Relative Strength")
            st.caption(
                "Compares this stock with SPY, QQQ, and an approximate "
                "sector ETF derived from the company’s SEC SIC classification."
            )

            rs_refresh = st.button(
                "Refresh Relative Strength",
                key=f"relative_strength_{selected_symbol}",
            )

            rs_resource = f"stock_report:{selected_symbol}:relative_strength"
            if rs_refresh:
                load_relative_strength.clear()
                relative_strength = force_refresh_resource(
                    rs_resource,
                    f"stock_report_rs_{selected_symbol}",
                    lambda: load_relative_strength(selected_symbol),
                    ttl_minutes=60,
                    loading_label=f"Refreshing relative strength for {selected_symbol}",
                )
            else:
                relative_strength = load_resource(
                    rs_resource,
                    f"stock_report_rs_{selected_symbol}",
                    lambda: load_relative_strength(selected_symbol),
                    ttl_minutes=60,
                    loading_label=f"Comparing {selected_symbol} with market benchmarks",
                )
            if relative_strength is None:
                render_loading_skeleton(rs_resource, rows=3, label=f"Comparing {selected_symbol} with market benchmarks")
                relative_strength = {"status": "Loading", "summary": "Relative strength is loading automatically."}

            if relative_strength.get("status") == "Available":
                rs_top = st.columns(4)
                rs_top[0].metric(
                    "RS Score",
                    relative_strength.get("score", "—"),
                )
                rs_top[1].metric(
                    "Verdict",
                    relative_strength.get("verdict", "—"),
                )
                rs_top[2].metric(
                    "RS Trend",
                    relative_strength.get("trend", "—"),
                )
                rs_top[3].metric(
                    "Sector",
                    relative_strength.get("sector_name", "—"),
                    relative_strength.get("sector_etf"),
                )

                st.write(relative_strength.get("summary", ""))

                rs_table = pd.DataFrame(
                    [
                        {
                            "Period": "5 Days",
                            "Stock Return %": relative_strength.get("stock_return_5d"),
                            "vs SPY %": relative_strength.get("vs_spy_5d"),
                            "vs QQQ %": relative_strength.get("vs_qqq_5d"),
                            "vs Sector %": relative_strength.get("vs_sector_5d"),
                        },
                        {
                            "Period": "20 Days",
                            "Stock Return %": relative_strength.get("stock_return_20d"),
                            "vs SPY %": relative_strength.get("vs_spy_20d"),
                            "vs QQQ %": relative_strength.get("vs_qqq_20d"),
                            "vs Sector %": relative_strength.get("vs_sector_20d"),
                        },
                        {
                            "Period": "60 Days",
                            "Stock Return %": relative_strength.get("stock_return_60d"),
                            "vs SPY %": relative_strength.get("vs_spy_60d"),
                            "vs QQQ %": relative_strength.get("vs_qqq_60d"),
                            "vs Sector %": relative_strength.get("vs_sector_60d"),
                        },
                    ]
                )
                st.dataframe(
                    rs_table,
                    width="stretch",
                    hide_index=True,
                )

                sic_description = relative_strength.get("sic_description")
                if sic_description:
                    st.caption(
                        f"Sector mapping source: SEC SIC "
                        f"{relative_strength.get('sic')} — {sic_description}. "
                        "Sector ETF classification is approximate and is used "
                        "as a comparison benchmark, not as a company profile."
                    )
            else:
                st.warning(relative_strength.get("summary", "Relative strength is unavailable."))

            # -------------------------
            # Smart Money Intelligence
            # -------------------------
            st.divider()
            st.subheader("Smart Money Intelligence")
            st.caption(
                "Combines institutional-style price/volume behavior with available "
                "options, insider, ownership, float, and delayed short-interest data."
            )

            smart_refresh = st.button(
                "Refresh Smart Money",
                key=f"smart_money_{selected_symbol}",
            )
            smart_resource = f"stock_report:{selected_symbol}:smart_money"

            def _load_stock_smart_money():
                try:
                    return load_smart_money(selected_symbol)
                except Exception:
                    return {
                        "status": "Unavailable",
                        "overall_score": None,
                        "verdict": "Unavailable",
                        "read_status": "Unavailable",
                        "coverage_pct": 0,
                        "available_modules": 0,
                        "total_modules": 5,
                        "summary": "Smart Money data could not be loaded from the connected providers.",
                    }

            if smart_refresh:
                load_smart_money.clear()
                st.session_state.smart_money_cache.pop(selected_symbol, None)
                smart_money_context = force_refresh_resource(
                    smart_resource,
                    f"stock_report_smart_money_{selected_symbol}",
                    _load_stock_smart_money,
                    ttl_minutes=30,
                    loading_label=f"Refreshing Smart Money data for {selected_symbol}",
                )
            else:
                smart_money_context = load_resource(
                    smart_resource,
                    f"stock_report_smart_money_{selected_symbol}",
                    _load_stock_smart_money,
                    ttl_minutes=30,
                    loading_label=f"Loading Smart Money data for {selected_symbol}",
                )
            if smart_money_context:
                st.session_state.smart_money_cache[selected_symbol] = smart_money_context

            if smart_money_context is None:
                render_loading_skeleton(smart_resource, rows=4, label=f"Loading Smart Money data for {selected_symbol}")
                smart_money_context = {
                    "status": "Not Loaded",
                    "overall_score": None,
                    "verdict": "Load to Analyze",
                    "read_status": "Not Loaded",
                    "coverage_pct": 0,
                    "available_modules": 0,
                    "total_modules": 5,
                    "institutional_activity": {},
                    "options_activity": {},
                    "insider_activity": {},
                    "ownership": {},
                    "float": {},
                    "summary": "Smart Money data is loading automatically for this ticker.",
                    "data_note": "Smart Money refreshes automatically and can also be refreshed manually.",
                }

            score_value = smart_money_context.get("overall_score")
            coverage_value = smart_money_context.get("coverage_pct")
            available_modules = smart_money_context.get("available_modules", 0)
            total_modules = smart_money_context.get("total_modules", 5)

            header_cols = st.columns(4)
            header_cols[0].metric("Smart Money Score", score_value if valid_value(score_value) else "—")
            header_cols[1].metric("Data Coverage", percent_text(coverage_value))
            header_cols[2].metric("Read Status", smart_money_context.get("read_status", "—"))
            header_cols[3].metric("Modules", f"{available_modules} / {total_modules}")
            st.markdown(f"**Verdict:** {smart_money_context.get('verdict', '—')}")
            st.write(smart_money_context.get("summary", ""))

            inst = smart_money_context.get("institutional_activity", {})
            opts = smart_money_context.get("options_activity", {})
            insiders = smart_money_context.get("insider_activity", {})
            ownership = smart_money_context.get("ownership", {})
            float_data = smart_money_context.get("float", {})

            status_line = []
            for label, section in [
                ("Accumulation", inst),
                ("Options", opts),
                ("Insiders", insiders),
                ("Ownership", ownership),
                ("Float", float_data),
            ]:
                status_line.append(f"{'✓' if section.get('status') == 'Available' else '—'} {label}")
            st.caption("  ·  ".join(status_line))

            sm_tabs = st.tabs([
                "Accumulation / Distribution",
                "Options Activity",
                "Insiders",
                "Ownership",
                "Float & Short Interest",
            ])

            with sm_tabs[0]:
                if inst.get("status") == "Available":
                    row = st.columns(3)
                    row[0].metric("Activity Score", inst.get("score", "—"))
                    row[1].metric("Verdict", inst.get("verdict", "—"))
                    row[2].metric("Up/Down Volume", inst.get("up_down_volume_ratio", "—"))
                    row2 = st.columns(2)
                    row2[0].metric("Accumulation Days", inst.get("accumulation_days", "—"))
                    row2[1].metric("Distribution Days", inst.get("distribution_days", "—"))
                    st.write(inst.get("summary", ""))
                    st.caption(f"Source: {inst.get('source', 'Calculated OHLCV')} · {inst.get('data_quality', 'Calculated / Inferred')}")
                    st.caption(inst.get("disclaimer", ""))
                else:
                    st.info(inst.get("summary", "Accumulation analysis is unavailable."))

            with sm_tabs[1]:
                if opts.get("status") == "Available":
                    st.caption(f"Data: {opts.get('data_source', 'Alpaca Indicative')} · {opts.get('data_quality', 'Delayed / Indicative')}")
                    row = st.columns(3)
                    row[0].metric("Activity Score", opts.get("score") if valid_value(opts.get("score")) else "—")
                    row[1].metric("Directional Read", opts.get("bias", "—"))
                    row[2].metric("Contracts Analyzed", compact_number(opts.get("contracts_analyzed")))
                    row2 = st.columns(3)
                    row2[0].metric("Avg. IV", percent_text(opts.get("average_implied_volatility_pct")))
                    row2[1].metric("Put/Call Activity", opts.get("put_call_activity_ratio") if valid_value(opts.get("put_call_activity_ratio")) else "—")
                    row2[2].metric("Leading Expiration", opts.get("most_active_expiration") or "—")
                    st.write(opts.get("summary", ""))
                    active_contracts = opts.get("active_contracts", [])
                    if active_contracts:
                        st.markdown("**Largest recent trade/quote-size candidates**")
                        st.dataframe(pd.DataFrame(active_contracts), width="stretch", hide_index=True)
                    else:
                        st.info("No larger recent trade or quote-size candidates were found in the returned chain.")
                    if opts.get("chain_truncated"):
                        st.warning("The chain reached the safety page limit, so this read may be incomplete.")
                    st.caption(opts.get("disclaimer", ""))
                else:
                    st.info(opts.get("summary", "Basic options activity is unavailable right now."))

            with sm_tabs[2]:
                if insiders.get("status") == "Available":
                    row = st.columns(3)
                    row[0].metric("Insider Score", insiders.get("score", "—"))
                    row[1].metric("Verdict", insiders.get("verdict", "—"))
                    row[2].metric("Transactions", insiders.get("transaction_count", "—"))
                    row2 = st.columns(2)
                    row2[0].metric("Purchases", money_text(insiders.get("purchase_value")))
                    row2[1].metric("Sales", money_text(insiders.get("sale_value")))
                    transactions = insiders.get("transactions", [])
                    if transactions:
                        st.dataframe(pd.DataFrame(transactions), width="stretch", hide_index=True)
                    st.caption(f"Source: {insiders.get('source', '—')} · {insiders.get('data_quality', 'Reported / Delayed')}")
                    st.caption(insiders.get("disclaimer", ""))
                else:
                    st.info(insiders.get("display_message") or insiders.get("summary", "Insider data is unavailable."))

            with sm_tabs[3]:
                if ownership.get("status") == "Available":
                    row = st.columns(3)
                    row[0].metric("Ownership Score", ownership.get("score", "—"))
                    row[1].metric("Institutional %", percent_text(ownership.get("institutional_ownership_pct")))
                    row[2].metric("Trend", ownership.get("trend", "—"))
                    row2 = st.columns(3)
                    row2[0].metric("Insider %", percent_text(ownership.get("insider_ownership_pct")))
                    row2[1].metric("Institutions", compact_number(ownership.get("institution_count")))
                    row2[2].metric("Institutional Shares", compact_number(ownership.get("institutional_shares")))
                    st.write(ownership.get("summary", ""))
                    st.caption(f"Source: {ownership.get('source') or 'Connected provider'} · {ownership.get('data_quality', 'Delayed / Reported')}")
                    st.caption(ownership.get("disclaimer", ""))
                else:
                    st.info(ownership.get("summary", "Ownership data is unavailable on the connected plans."))

            with sm_tabs[4]:
                if float_data.get("status") == "Available":
                    row = st.columns(3)
                    row[0].metric("Float", compact_number(float_data.get("float_shares")))
                    row[1].metric("Shares Outstanding", compact_number(float_data.get("shares_outstanding")))
                    row[2].metric("Float Type", float_data.get("float_category", "—"))
                    row2 = st.columns(3)
                    row2[0].metric("Short % Float", percent_text(float_data.get("short_interest_pct_float")))
                    row2[1].metric("Days to Cover", float_data.get("days_to_cover") if valid_value(float_data.get("days_to_cover")) else "—")
                    row2[2].metric("Short Risk", float_data.get("short_risk") or "—")
                    row3 = st.columns(3)
                    row3[0].metric("Shares Short", compact_number(float_data.get("shares_short")))
                    row3[1].metric("Short Interest Change", percent_text(float_data.get("short_interest_change_pct")))
                    row3[2].metric("Squeeze Score", float_data.get("squeeze_score") if valid_value(float_data.get("squeeze_score")) else "—")
                    st.write(float_data.get("summary", ""))
                    st.caption(f"Source: {float_data.get('source') or 'Connected provider'} · {float_data.get('data_quality', 'Delayed / Reported')}")
                    st.caption(float_data.get("disclaimer", ""))
                else:
                    st.info(float_data.get("summary", "Float and short-interest data is unavailable."))

            st.caption(smart_money_context.get("data_note", ""))

            # -------------------------
            # Trading Intelligence
            # -------------------------
            st.divider()
            st.subheader("Trading Intelligence")
            st.caption(
                "Pattern recognition, trend health, multi-timeframe alignment, "
                "entry quality, adaptive stops, target intelligence, exit warnings, "
                "and same-symbol historical analogues."
            )

            trade_refresh = st.button(
                "Refresh Trading Intelligence",
                key=f"trade_intelligence_{selected_symbol}",
            )
            trade_resource = f"stock_report:{selected_symbol}:trading_intelligence"
            stock_payload = normalize_stock_payload(selected_stock)

            def _load_stock_trade_intelligence():
                try:
                    return load_trade_intelligence(selected_symbol, stock_payload)
                except Exception:
                    return {
                        "overall_score": None,
                        "status": "Unavailable",
                        "pattern": {},
                        "trend_health": {},
                        "multi_timeframe": {},
                        "entry_quality": {},
                        "adaptive_stops": {},
                        "targets": {"targets": []},
                        "exit_management": {},
                        "historical_setup": {},
                    }

            if trade_refresh:
                load_trade_intelligence.clear()
                st.session_state.trade_intelligence_cache.pop(selected_symbol, None)
                trade_intelligence_context = force_refresh_resource(
                    trade_resource,
                    f"stock_report_trade_intelligence_{selected_symbol}",
                    _load_stock_trade_intelligence,
                    ttl_minutes=30,
                    loading_label=f"Refreshing trading structure for {selected_symbol}",
                )
            else:
                trade_intelligence_context = load_resource(
                    trade_resource,
                    f"stock_report_trade_intelligence_{selected_symbol}",
                    _load_stock_trade_intelligence,
                    ttl_minutes=30,
                    loading_label=f"Analyzing trading structure for {selected_symbol}",
                )
            if trade_intelligence_context:
                st.session_state.trade_intelligence_cache[selected_symbol] = trade_intelligence_context

            if trade_intelligence_context is None:
                render_loading_skeleton(trade_resource, rows=4, label=f"Analyzing trading structure for {selected_symbol}")
                trade_intelligence_context = {
                    "overall_score": None,
                    "status": "Not Loaded",
                    "pattern": {},
                    "trend_health": {},
                    "multi_timeframe": {},
                    "entry_quality": {},
                    "adaptive_stops": {},
                    "targets": {"targets": []},
                    "exit_management": {},
                    "historical_setup": {},
                }

            # v0.95A: Resolve and persist one canonical analysis object. Existing
            # engines remain untouched; all downstream plan consumers use this
            # single resolved plan instead of repeating fallback calculations.
            canonical_analysis = build_canonical_analysis(
                selected_symbol,
                dict(selected_stock),
                trading_intelligence=trade_intelligence_context,
                market_context=report_market or {},
                smart_money_context=smart_money_context or {},
                ai_report=st.session_state.ai_research_reports.get(selected_symbol, {}),
            )
            st.session_state.canonical_analysis_cache[selected_symbol] = canonical_analysis.to_dict()
            try:
                save_analysis(canonical_analysis)
            except Exception:
                pass

            ti_top = st.columns(4)
            ti_top[0].metric("Trading Intelligence", trade_intelligence_context.get("overall_score") if valid_value(trade_intelligence_context.get("overall_score")) else "—")
            ti_top[1].metric("Status", trade_intelligence_context.get("status", "—"))
            ti_top[2].metric("Entry Grade", trade_intelligence_context.get("entry_quality", {}).get("grade", "—"))
            ti_top[3].metric("MTF Alignment", trade_intelligence_context.get("multi_timeframe", {}).get("alignment", "—"))

            ti_tabs = st.tabs([
                "Pattern & Trend",
                "Multi-Timeframe",
                "Entry & Stops",
                "Targets",
                "Exit Management",
                "Historical Setup",
            ])

            pattern_data = trade_intelligence_context.get("pattern", {})
            trend_data = trade_intelligence_context.get("trend_health", {})
            with ti_tabs[0]:
                row = st.columns(4)
                row[0].metric("Primary Pattern", pattern_data.get("primary_pattern", "—"))
                row[1].metric("Pattern Score", pattern_data.get("pattern_score") if valid_value(pattern_data.get("pattern_score")) else "—")
                row[2].metric("Pattern Maturity", pattern_data.get("maturity", "—"))
                row[3].metric("Trend Health", trend_data.get("score") if valid_value(trend_data.get("score")) else "—", trend_data.get("rating", "—"))
                patterns = pattern_data.get("patterns", [])
                if patterns:
                    st.dataframe(pd.DataFrame(patterns), width="stretch", hide_index=True)
                if trend_data.get("strengths"):
                    st.markdown("**Trend strengths**")
                    for item in trend_data.get("strengths", []): st.write(f"• {item}")
                if trend_data.get("warnings"):
                    st.markdown("**Trend warnings**")
                    for item in trend_data.get("warnings", []): st.write(f"• {item}")

            mtf_data = trade_intelligence_context.get("multi_timeframe", {})
            with ti_tabs[1]:
                st.metric("Alignment Score", mtf_data.get("alignment_score") if valid_value(mtf_data.get("alignment_score")) else "—", mtf_data.get("alignment", "—"))
                rows = []
                for timeframe, details in mtf_data.get("timeframes", {}).items():
                    rows.append({"Timeframe": timeframe, "Trend": details.get("trend"), "Score": details.get("score"), "Close": details.get("close")})
                if rows:
                    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

            entry_data = trade_intelligence_context.get("entry_quality", {})
            stop_data = trade_intelligence_context.get("adaptive_stops", {})
            with ti_tabs[2]:
                row = st.columns(3)
                row[0].metric("Entry Score", entry_data.get("score") if valid_value(entry_data.get("score")) else "—")
                row[1].metric("Entry Grade", entry_data.get("grade", "—"))
                row[2].metric("Entry Status", entry_data.get("status", "—"))
                stop_row = st.columns(3)
                stop_row[0].metric("Aggressive Stop", money_text(stop_data.get("aggressive")))
                stop_row[1].metric("Standard Stop", money_text(stop_data.get("standard")))
                stop_row[2].metric("Conservative Stop", money_text(stop_data.get("conservative")))
                if entry_data.get("reasons"):
                    st.markdown("**Why the entry scores well**")
                    for item in entry_data.get("reasons", []): st.write(f"• {item}")
                if entry_data.get("warnings"):
                    st.markdown("**Entry concerns**")
                    for item in entry_data.get("warnings", []): st.write(f"• {item}")

            with ti_tabs[3]:
                target_rows = trade_intelligence_context.get("targets", {}).get("targets", [])
                if target_rows:
                    st.dataframe(pd.DataFrame(target_rows), width="stretch", hide_index=True)
                measured = trade_intelligence_context.get("targets", {}).get("measured_move_reference")
                st.metric("Measured-Move Reference", money_text(measured))

            exit_data = trade_intelligence_context.get("exit_management", {})
            with ti_tabs[4]:
                st.metric("Warning Severity", exit_data.get("severity", "—"))
                if exit_data.get("warnings"):
                    st.markdown("**Current warnings**")
                    for item in exit_data.get("warnings", []): st.write(f"• {item}")
                if exit_data.get("management_actions"):
                    st.markdown("**Management ideas**")
                    for item in exit_data.get("management_actions", []): st.write(f"• {item}")

            history_data = trade_intelligence_context.get("historical_setup", {})
            with ti_tabs[5]:
                row = st.columns(4)
                row[0].metric("Samples", history_data.get("sample_size", 0))
                row[1].metric("Win Rate", percent_text(history_data.get("win_rate")))
                row[2].metric("Avg. Return", percent_text(history_data.get("average_return")))
                row[3].metric("Avg. Drawdown", percent_text(history_data.get("average_drawdown")))
                st.caption(history_data.get("note", ""))

            if trade_intelligence_context.get("overall_score") is not None:
                if st.button("Send to Trade Planner", key=f"send_to_planner_{selected_symbol}"):
                    st.session_state.trade_plan_prefill = planner_prefill(canonical_analysis)
                    navigate_to("Trade Planner", symbol=selected_symbol)

            # -------------------------
            # Canonical MomoPro Plan
            # -------------------------
            st.divider()
            st.subheader("Official MomoPro Plan")
            st.caption("v0.95A single source of truth used by Stock Report, Trade Planner, and future integrations.")
            canonical_plan = canonical_analysis.plan
            cp1 = st.columns(4)
            entry_display = canonical_plan.reference_entry
            if valid_value(canonical_plan.entry_low) and valid_value(canonical_plan.entry_high) and canonical_plan.entry_low != canonical_plan.entry_high:
                entry_display = f"{money_text(canonical_plan.entry_low)} – {money_text(canonical_plan.entry_high)}"
            else:
                entry_display = money_text(canonical_plan.reference_entry)
            cp1[0].metric("Official Entry", entry_display)
            cp1[1].metric("Official Stop", money_text(canonical_plan.stop))
            cp1[2].metric("Official T1", money_text(canonical_plan.t1))
            cp1[3].metric("Official T2", money_text(canonical_plan.t2))
            cp2 = st.columns(4)
            cp2[0].metric("Official T3", money_text(canonical_plan.t3))
            cp2[1].metric("Setup", canonical_analysis.setup or "—")
            cp2[2].metric("Grade", canonical_analysis.grade or "—")
            cp2[3].metric("Plan Source", canonical_plan.source)

            # -------------------------
            # Momo Engine Confidence
            # -------------------------
            st.divider()

            st.subheader("Momo Engine Confidence")

            integrated_confidence = calculate_integrated_confidence(
                technical_confidence=selected_stock.get("Momo Confidence"),
                market_context=report_market,
                relative_strength=relative_strength,
                smart_money_context=smart_money_context,
                trade_intelligence_context=trade_intelligence_context,
            )

            confidence_columns = st.columns(4)
            confidence_columns[0].metric(
                "Technical Confidence",
                percent_text(selected_stock.get("Momo Confidence")),
                selected_stock.get("Confidence Rating", "—"),
            )
            confidence_columns[1].metric(
                "Market-Adjusted",
                percent_text(integrated_confidence.get("Integrated Confidence")),
                integrated_confidence.get("Integrated Rating", "—"),
            )
            confidence_columns[2].metric(
                "Market Component",
                percent_text(
                    integrated_confidence.get("Integrated Breakdown", {}).get("Market")
                ),
            )
            confidence_columns[3].metric(
                "Relative Strength",
                percent_text(
                    integrated_confidence.get("Integrated Breakdown", {}).get(
                        "Relative Strength"
                    )
                ),
            )

            adjustment = integrated_confidence.get("Adjustment")
            if adjustment is not None:
                direction = "raised" if adjustment > 0 else "lowered" if adjustment < 0 else "left unchanged"
                st.caption(
                    f"Market, sector, and relative-strength context {direction} "
                    f"the technical confidence by {abs(adjustment):.0f} point(s)."
                )
            else:
                st.caption(
                    "Market-adjusted confidence will populate after Market Context "
                    "and Relative Strength are available."
                )

            with st.expander(
                "See confidence breakdown"
            ):
                confidence_breakdown = [
                    (
                        "Trend",
                        "Trend Confidence",
                    ),
                    (
                        "Location",
                        "Location Confidence",
                    ),
                    (
                        "Momentum",
                        "Momentum Confidence",
                    ),
                    (
                        "Volume",
                        "Volume Confidence",
                    ),
                    (
                        "Opportunity",
                        "Opportunity Confidence",
                    ),
                    (
                        "Risk",
                        "Risk Confidence",
                    ),
                    (
                        "Structure",
                        "Structure Confidence",
                    ),
                ]

                context_breakdown = integrated_confidence.get(
                    "Integrated Breakdown", {}
                )
                context_row = st.columns(6)
                context_row[0].metric(
                    "Technical", percent_text(context_breakdown.get("Technical"))
                )
                context_row[1].metric(
                    "Market", percent_text(context_breakdown.get("Market"))
                )
                context_row[2].metric(
                    "Sector", percent_text(context_breakdown.get("Sector"))
                )
                context_row[3].metric(
                    "Relative Strength",
                    percent_text(context_breakdown.get("Relative Strength")),
                )
                context_row[4].metric(
                    "Smart Money",
                    percent_text(context_breakdown.get("Smart Money")),
                )
                context_row[5].metric(
                    "Trading Intelligence",
                    percent_text(context_breakdown.get("Trading Intelligence")),
                )
                st.markdown("**Technical module breakdown**")

                first_row = st.columns(4)
                second_row = st.columns(3)

                for index, (label, key) in enumerate(
                    confidence_breakdown
                ):
                    column = (
                        first_row[index]
                        if index < 4
                        else second_row[index - 4]
                    )

                    column.metric(
                        label,
                        percent_text(
                            selected_stock.get(key)
                        ),
                    )

            # -------------------------
            # Latest News
            # -------------------------
            st.divider()
            st.subheader("Latest News")
            st.caption("Top recent headlines for this stock. Open the News tab for full research.")
            try:
                selected_news = rank_news(load_ticker_news(selected_symbol))
                selected_news_summary = summarize_news(selected_news)
                news_metrics = st.columns(3)
                news_metrics[0].metric("News Sentiment", selected_news_summary.get("overall_sentiment", "—"))
                news_metrics[1].metric("High Impact", selected_news_summary.get("high_impact", 0))
                news_metrics[2].metric("Recent Headlines", len(selected_news))
                source_counts = selected_news_summary.get("source_counts", {})
                if source_counts:
                    st.caption(
                        "Coverage: "
                        + " · ".join(
                            f"{source}: {count}"
                            for source, count in sorted(
                                source_counts.items(),
                                key=lambda pair: pair[1],
                                reverse=True,
                            )
                        )
                    )

                for item in selected_news[:5]:
                    if item.get("url"):
                        st.markdown(f'**[{item.get("headline")}]({item.get("url")})**')
                    else:
                        st.markdown(f'**{item.get("headline")}**')
                    st.caption(
                        f'{item.get("category")} · {item.get("impact")} impact · '
                        f'{item.get("sentiment")} · {item.get("source")}'
                    )
                    st.write(item.get("why_it_matters", ""))
            except Exception as error:
                selected_news = []
                st.warning(f"Stock news could not be loaded: {error}")

            # -------------------------
            # Engine and AI Decisions
            # -------------------------
            st.divider()

            st.subheader("Decision Center")

            engine_decision = build_momo_engine_decision(
                selected_stock,
                market_context=report_market,
                relative_strength=relative_strength,
                news_context={
                    "summary": summarize_news(selected_news),
                    "headlines": selected_news[:10],
                },
                smart_money_context=smart_money_context,
                trade_intelligence_context=trade_intelligence_context,
            )

            engine_col, ai_col = st.columns(2)

            with engine_col:
                st.markdown("### Momo Engine Decision")
                st.metric(
                    "Rule-Based Decision",
                    engine_decision["decision"],
                )
                st.write(engine_decision["summary"])

                if engine_decision["strengths"]:
                    st.markdown("**What the engine likes**")
                    for item in engine_decision["strengths"]:
                        st.write(f"• {item}")

                if engine_decision["concerns"]:
                    st.markdown("**Main concerns**")
                    for item in engine_decision["concerns"]:
                        st.write(f"• {item}")

                with st.expander("Engine confirmation and invalidation"):
                    st.markdown("**What would strengthen it**")
                    for item in engine_decision["confirmation"]:
                        st.write(f"• {item}")

                    st.markdown("**What would invalidate it**")
                    for item in engine_decision["invalidation"]:
                        st.write(f"• {item}")

            with ai_col:
                st.markdown("### Independent AI Decision")
                st.caption(
                    "The AI uses the technical, market, relative-strength, "
                    "verified news, and available Smart Money data in this report."
                )

                cached_ai = st.session_state.ai_commentary_cache.get(
                    selected_symbol
                )

                button_label = (
                    "Refresh AI Decision"
                    if cached_ai
                    else "Generate AI Decision"
                )

                if st.button(
                    button_label,
                    key=f"generate_ai_{selected_symbol}",
                    width="stretch",
                ):
                    try:
                        api_key = st.secrets["OPENAI_API_KEY"]

                        with st.spinner(
                            f"AI is analyzing {selected_symbol}..."
                        ):
                            cached_ai = generate_ai_decision(
                                api_key=api_key,
                                stock=selected_stock,
                                market_context=report_market,
                                relative_strength=relative_strength,
                                news_context={
                                    "summary": summarize_news(selected_news),
                                    "headlines": selected_news[:10],
                                },
                                smart_money_context=smart_money_context,
                                trade_intelligence_context=trade_intelligence_context,
                            )

                        st.session_state.ai_commentary_cache[
                            selected_symbol
                        ] = cached_ai

                    except KeyError:
                        st.error(
                            "OPENAI_API_KEY is missing from Streamlit "
                            "secrets."
                        )
                    except Exception as error:
                        st.error(
                            "The AI decision could not be generated. "
                            f"Details: {error}"
                        )

                if cached_ai:
                    st.metric(
                        "AI Decision",
                        cached_ai["decision"],
                        f'{cached_ai["confidence"]}% AI confidence',
                    )

                    st.write(cached_ai["summary"])

                    if cached_ai["strengths"]:
                        st.markdown("**AI strengths**")
                        for item in cached_ai["strengths"]:
                            st.write(f"• {item}")

                    if cached_ai["concerns"]:
                        st.markdown("**AI concerns**")
                        for item in cached_ai["concerns"]:
                            st.write(f"• {item}")

                    with st.expander("AI improvement and invalidation"):
                        st.markdown("**What would improve the setup**")
                        for item in cached_ai["what_improves_setup"]:
                            st.write(f"• {item}")

                        st.markdown("**What would invalidate it**")
                        for item in cached_ai["invalidation"]:
                            st.write(f"• {item}")
                else:
                    st.info(
                        "Generate the AI Decision when you want an "
                        "independent second opinion. It runs only on "
                        "demand, so scanning the market does not create "
                        "an API charge for every stock."
                    )

            # -------------------------
            # Support / Resistance v2
            # -------------------------
            st.divider()

            st.subheader(
                "Support and Resistance"
            )

            st.caption(
                "Zones are based on "
                "historical swing reactions, "
                "touch count, candle rejection, "
                "volume interaction, and recency."
            )

            (
                support_col,
                resistance_col,
            ) = st.columns(2)

            with support_col:
                st.markdown(
                    "#### Support"
                )

                for label in [
                    "Support 1",
                    "Support 2",
                    "Support 3",
                ]:
                    value = (
                        selected_stock.get(
                            label
                        )
                    )

                    quality = (
                        selected_stock.get(
                            f"{label} Quality"
                        )
                    )

                    touches = (
                        selected_stock.get(
                            f"{label} Touches"
                        )
                    )

                    if valid_value(value):
                        st.metric(
                            label,
                            money_text(value),
                        )

                        reaction = (
                            reaction_text(
                                quality,
                                touches,
                            )
                        )

                        if reaction:
                            st.caption(
                                reaction
                            )

                    else:
                        st.write(
                            f"{label}: "
                            "Not available"
                        )

            with resistance_col:
                st.markdown(
                    "#### Resistance"
                )

                for label in [
                    "Resistance 1",
                    "Resistance 2",
                    "Resistance 3",
                ]:
                    value = (
                        selected_stock.get(
                            label
                        )
                    )

                    quality = (
                        selected_stock.get(
                            f"{label} Quality"
                        )
                    )

                    touches = (
                        selected_stock.get(
                            f"{label} Touches"
                        )
                    )

                    if valid_value(value):
                        upside = (
                            (
                                float(value)
                                - float(
                                    selected_stock[
                                        "Close"
                                    ]
                                )
                            )
                            / float(
                                selected_stock[
                                    "Close"
                                ]
                            )
                        ) * 100

                        st.metric(
                            label,
                            money_text(value),
                            (
                                f"{upside:.1f}% "
                                "upside"
                            ),
                        )

                        reaction = (
                            reaction_text(
                                quality,
                                touches,
                            )
                        )

                        if reaction:
                            st.caption(
                                reaction
                            )

                    else:
                        st.write(
                            f"{label}: "
                            "Not available"
                        )

            # -------------------------
            # Risk / Reward
            # -------------------------
            st.divider()

            st.subheader(
                "Structural Risk / Reward"
            )

            rr_columns = st.columns(4)

            reference_entry = (
                selected_stock.get(
                    "Reference Entry"
                )
            )

            risk_reference = (
                selected_stock.get(
                    "Risk Reference"
                )
            )

            reward_reference = (
                selected_stock.get(
                    "Reward Reference"
                )
            )

            risk_reward = (
                selected_stock.get(
                    "Risk Reward"
                )
            )

            rr_columns[0].metric(
                "Reference Entry",
                money_text(
                    reference_entry
                ),
            )

            rr_columns[1].metric(
                "Risk Reference",
                money_text(
                    risk_reference
                ),
            )

            rr_columns[2].metric(
                "Reward Reference",
                money_text(
                    reward_reference
                ),
            )

            rr_columns[3].metric(
                "Risk / Reward",
                r_text(
                    risk_reward
                ),
            )

            risk_detail_columns = (
                st.columns(3)
            )

            risk_per_share = (
                selected_stock.get(
                    "Risk Per Share"
                )
            )

            reward_per_share = (
                selected_stock.get(
                    "Reward Per Share"
                )
            )

            rr_status = (
                selected_stock.get(
                    "Risk Reward Status",
                    "Not available",
                )
            )

            risk_detail_columns[0].metric(
                "Risk Per Share",
                money_text(
                    risk_per_share
                ),
            )

            risk_detail_columns[1].metric(
                "Reward Per Share",
                money_text(
                    reward_per_share
                ),
            )

            risk_detail_columns[2].metric(
                "Structure Rating",
                rr_status,
            )

            st.caption(
                "This is a structural "
                "reference using the current "
                "close, nearest confirmed "
                "support zone, and nearest "
                "confirmed resistance zone."
            )

            # -------------------------
            # T1 / T2 / T3
            # -------------------------
            st.divider()

            st.subheader(
                "Structural Targets"
            )

            target_columns = st.columns(3)

            for index, column in enumerate(
                target_columns,
                start=1,
            ):
                target_name = f"T{index}"

                target_value = (
                    selected_stock.get(
                        target_name
                    )
                )

                target_upside = (
                    selected_stock.get(
                        f"{target_name} "
                        "Upside %"
                    )
                )

                target_r = (
                    selected_stock.get(
                        f"{target_name} R"
                    )
                )

                with column:
                    st.markdown(
                        f"#### {target_name}"
                    )

                    st.metric(
                        "Target Price",
                        money_text(
                            target_value
                        ),
                    )

                    st.metric(
                        "Upside",
                        percent_text(
                            target_upside
                        ),
                    )

                    st.metric(
                        "Reward / Risk",
                        r_text(
                            target_r
                        ),
                    )

            st.caption(
                "T1, T2, and T3 use the "
                "three upgraded structural "
                "resistance zones. No target "
                "is invented when a valid "
                "zone is unavailable."
            )

            st.info(
                "Market Context integration is active. Technical, market, "
                "sector, and relative-strength inputs now work together."
            )

    elif df is not None:
        st.warning(
            "The scan completed, but no "
            "qualifying stocks were found."
        )


# -----------------------------
# News
# -----------------------------
if active_page_is("News"):
    st.header("News")
    render_freshness("market_news", ttl_minutes=_data_cache_minutes("news", 15), label="Market news")
    st.caption(
        "Centralized market and stock-specific news intelligence. Search any ticker, "
        "even if it did not appear in the scanner."
    )

    news_mode = st.radio(
        "News view",
        ["Market News", "Ticker Research"],
        horizontal=True,
        key="news_mode",
    )

    if news_mode == "Market News":
        if st.button("Refresh Market News", key="refresh_market_news"):
            load_market_news.clear()
            force_refresh_resource(
                "market_news", "dashboard_headlines", _load_ranked_market_news_for_page,
                ttl_minutes=_data_cache_minutes("news", 15), loading_label="Refreshing market news",
            )
            st.info("Market news refresh started.")

        try:
            market_news = list(st.session_state.get("dashboard_headlines") or [])
            if not market_news:
                render_loading_skeleton("market_news", rows=5, label="Loading current market news")
                st.info("Market news is loading automatically.")
            market_summary = summarize_news(market_news)
            summary_cols = st.columns(5)
            summary_cols[0].metric("Overall", market_summary.get("overall_sentiment", "—"))
            summary_cols[1].metric("Bullish", market_summary.get("bullish", 0))
            summary_cols[2].metric("Bearish", market_summary.get("bearish", 0))
            summary_cols[3].metric("Mixed", market_summary.get("mixed", 0))
            summary_cols[4].metric("High Impact", market_summary.get("high_impact", 0))
            source_counts = market_summary.get("source_counts", {})
            if source_counts:
                st.caption(
                    "Combined provider coverage: "
                    + " · ".join(
                        f"{source}: {count}"
                        for source, count in sorted(
                            source_counts.items(),
                            key=lambda pair: pair[1],
                            reverse=True,
                        )
                    )
                )

            filter_cols = st.columns(3)
            sentiment_filter = filter_cols[0].selectbox(
                "Sentiment", ["All", "Bullish", "Bearish", "Mixed", "Neutral"]
            )
            impact_filter = filter_cols[1].selectbox(
                "Impact", ["All", "High", "Medium", "Low"]
            )
            category_options = ["All"] + sorted({item.get("category", "General") for item in market_news})
            category_filter = filter_cols[2].selectbox("Category", category_options)

            filtered_news = [
                item for item in market_news
                if (sentiment_filter == "All" or item.get("sentiment") == sentiment_filter)
                and (impact_filter == "All" or item.get("impact") == impact_filter)
                and (category_filter == "All" or item.get("category") == category_filter)
            ]

            for item in filtered_news[:40]:
                if item.get("url"):
                    st.markdown(f'### [{item.get("headline")}]({item.get("url")})')
                else:
                    st.markdown(f'### {item.get("headline")}')
                st.caption(
                    f'{item.get("category")} · {item.get("impact")} impact · '
                    f'{item.get("sentiment")} · {item.get("source")} · '
                    f'Symbols: {", ".join(item.get("symbols") or []) or "Market-wide"}'
                )
                st.write(item.get("why_it_matters", ""))
                st.divider()
        except Exception as error:
            st.error(f"Market news could not be loaded: {error}")

    else:
        default_symbol = st.session_state.selected_symbol or st.session_state.news_search_symbol
        searched_symbol = st.text_input(
            "Ticker",
            value=default_symbol,
            placeholder="AAPL",
            key="news_ticker_input",
        ).strip().upper()

        if searched_symbol:
            st.session_state.news_search_symbol = searched_symbol
            refresh_cols = st.columns(2)
            if refresh_cols[0].button("Refresh Ticker News", key=f"refresh_news_{searched_symbol}"):
                load_ticker_news.clear()
                load_sec_filings.clear()

            try:
                ticker_news = rank_news(load_ticker_news(searched_symbol))
                ticker_summary = summarize_news(ticker_news)
                sec_data = load_sec_filings(searched_symbol)
                company_name = sec_data.get("company")
                fda_data = load_fda_records(company_name) if company_name else {"status": "Unavailable", "records": []}

                head = st.columns(5)
                head[0].metric("Ticker", searched_symbol)
                head[1].metric("Overall Sentiment", ticker_summary.get("overall_sentiment", "—"))
                head[2].metric("Bullish", ticker_summary.get("bullish", 0))
                head[3].metric("Bearish", ticker_summary.get("bearish", 0))
                head[4].metric("High Impact", ticker_summary.get("high_impact", 0))
                source_counts = ticker_summary.get("source_counts", {})
                if source_counts:
                    st.caption(
                        "Combined provider coverage: "
                        + " · ".join(
                            f"{source}: {count}"
                            for source, count in sorted(
                                source_counts.items(),
                                key=lambda pair: pair[1],
                                reverse=True,
                            )
                        )
                    )

                if st.button(
                    "Generate AI Catalyst Analysis",
                    key=f"news_ai_{searched_symbol}",
                    width="stretch",
                ):
                    try:
                        with st.spinner(f"AI is analyzing news and catalysts for {searched_symbol}..."):
                            st.session_state.news_ai_cache[searched_symbol] = analyze_news(
                                st.secrets["OPENAI_API_KEY"],
                                searched_symbol,
                                ticker_news,
                                sec_data.get("filings", []),
                                fda_data.get("records", []),
                            )
                    except Exception as error:
                        st.error(f"AI catalyst analysis failed: {error}")

                cached_news_ai = st.session_state.news_ai_cache.get(searched_symbol)
                if cached_news_ai:
                    st.subheader("AI Catalyst Summary")
                    ai_cols = st.columns(3)
                    ai_cols[0].metric("Sentiment", cached_news_ai.get("overall_sentiment", "—"))
                    ai_cols[1].metric("Impact", cached_news_ai.get("impact", "—"))
                    ai_cols[2].metric("Confidence", f'{cached_news_ai.get("confidence", 0)}%')
                    st.write(cached_news_ai.get("catalyst_summary", ""))
                    bull_col, bear_col = st.columns(2)
                    with bull_col:
                        st.markdown("**Bullish factors**")
                        for item in cached_news_ai.get("bullish_factors", []):
                            st.write(f"• {item}")
                    with bear_col:
                        st.markdown("**Bearish factors**")
                        for item in cached_news_ai.get("bearish_factors", []):
                            st.write(f"• {item}")

                st.subheader("Recent Headlines")
                for item in ticker_news[:30]:
                    if item.get("url"):
                        st.markdown(f'**[{item.get("headline")}]({item.get("url")})**')
                    else:
                        st.markdown(f'**{item.get("headline")}**')
                    st.caption(
                        f'{item.get("category")} · {item.get("impact")} impact · '
                        f'{item.get("sentiment")} · {item.get("source")}'
                    )
                    st.write(item.get("why_it_matters", ""))

                st.divider()
                st.subheader("SEC Filings")
                if sec_data.get("filings"):
                    for filing in sec_data.get("filings", []):
                        st.markdown(
                            f'**[{filing.get("form")} — {filing.get("date")}]({filing.get("url")})**'
                        )
                        st.caption(filing.get("description", ""))
                else:
                    st.caption("No recent priority SEC filings were returned.")

                st.divider()
                st.subheader("FDA Enforcement / Recall Records")
                if fda_data.get("records"):
                    for record in fda_data.get("records", []):
                        st.markdown(
                            f'**{record.get("classification", "FDA record")} — '
                            f'{record.get("report_date", "")}**'
                        )
                        st.write(record.get("reason", ""))
                        st.caption(record.get("product", ""))
                else:
                    st.caption(
                        "No matching openFDA drug-enforcement records were found for the SEC company name. "
                        "This does not mean there are no FDA developments; clinical and approval headlines "
                        "are also classified from the news feed above."
                    )
            except Exception as error:
                st.error(f"Ticker research could not be loaded: {error}")
        else:
            st.info("Enter a ticker to load stock-specific news, SEC filings, FDA records, and AI catalyst analysis.")



def render_ai_summary_header(symbol, grade, confidence, momo_decision, rs_verdict):
    st.markdown(
        """
        <style>
        .momo-ai-grid-card {
            border: 1px solid rgba(128,128,128,.28);
            border-radius: 12px;
            padding: .85rem 1rem;
            min-height: 92px;
            overflow-wrap: anywhere;
        }
        .momo-ai-grid-label {
            font-size: .78rem;
            opacity: .72;
            margin-bottom: .35rem;
        }
        .momo-ai-grid-value {
            font-size: 1.18rem;
            font-weight: 650;
            line-height: 1.25;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        @media (max-width: 900px) {
            .momo-ai-grid-value { font-size: 1rem; }
            .momo-ai-grid-card { min-height: 76px; padding: .7rem .8rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    values = [
        ("Ticker", symbol),
        ("Grade", grade),
        ("Technical Confidence", confidence),
        ("Momo Engine", momo_decision),
        ("Relative Strength", rs_verdict),
    ]
    cols = st.columns(5)
    for col, (label, value) in zip(cols, values):
        with col:
            st.markdown(
                f"""
                <div class="momo-ai-grid-card">
                    <div class="momo-ai-grid-label">{label}</div>
                    <div class="momo-ai-grid-value">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# -----------------------------
# AI Analysis
# -----------------------------
if active_page_is("AI Analysis"):
    st.header("AI Analysis")
    st.caption(
        "Independent AI research that uses MomoPro evidence, forms its own "
        "opinion, explains disagreements, and answers follow-up questions."
    )

    st.subheader("🌎 Global Ask Momo AI")
    st.caption(
        "Always available. Ask about any stock, the broader market, current news, "
        "trade ideas, comparisons, or trading concepts. Independent research comes "
        "first; MomoPro is used only as an additional reference."
    )

    global_history = st.session_state.global_ai_history
    for message in global_history:
        with st.chat_message(message.get("role", "assistant")):
            st.write(message.get("content", ""))

    with st.form("global_momo_ai_form", clear_on_submit=True):
        global_question = st.text_area(
            "Ask anything",
            placeholder=(
                "Examples: What are the strongest swing setups right now? "
                "Research Nike. Compare AMD and NVDA. What is driving the market today?"
            ),
            height=90,
        )
        global_submit = st.form_submit_button(
            "Research and Answer",
            type="primary",
            width="stretch",
        )

    global_controls = st.columns([1, 3])
    with global_controls[0]:
        if st.button(
            "Clear Global Chat",
            key="clear_global_ai_chat",
            width="stretch",
        ):
            st.session_state.global_ai_history = []
            st.session_state.global_ai_last_meta = {}
            st.rerun()

    if global_submit and global_question.strip():
        scan_reference = []
        current_scan = st.session_state.scan_results
        if current_scan is not None and not current_scan.empty:
            preferred_columns = [
                column
                for column in [
                    "Symbol",
                    "Grade",
                    "Momo Score",
                    "Dee Fit",
                    "Momo Confidence",
                    "Setup",
                    "Price",
                    "RVOL",
                    "ATR %",
                ]
                if column in current_scan.columns
            ]
            if preferred_columns:
                scan_reference = (
                    current_scan[preferred_columns]
                    .head(30)
                    .to_dict(orient="records")
                )

        global_history.append(
            {"role": "user", "content": global_question.strip()}
        )
        try:
            with st.spinner(
                "Global Momo AI is independently researching the market and web..."
            ):
                from global_ai import answer_global_question

                result = answer_global_question(
                    api_key=_secret("OPENAI_API_KEY"),
                    question=global_question.strip(),
                    conversation=global_history[:-1],
                    alpaca_api_key=st.secrets["ALPACA_API_KEY"],
                    alpaca_secret_key=st.secrets["ALPACA_SECRET_KEY"],
                    alpha_vantage_api_key=_secret("ALPHA_VANTAGE_API_KEY"),
                    finnhub_api_key=_secret("FINNHUB_API_KEY"),
                    fmp_api_key=_secret("FMP_API_KEY"),
                    momo_scan_reference=scan_reference,
                    market_context=st.session_state.market_context,
                )
            global_history.append(
                {"role": "assistant", "content": result["answer"]}
            )
            st.session_state.global_ai_history = global_history
            st.session_state.global_ai_last_meta = result
            st.rerun()
        except Exception as exc:
            global_history.append(
                {
                    "role": "assistant",
                    "content": f"I could not complete the independent research: {exc}",
                }
            )
            st.session_state.global_ai_history = global_history
            st.rerun()

    global_meta = st.session_state.global_ai_last_meta
    if global_meta:
        web_status = (
            "Web research used"
            if global_meta.get("used_web_search")
            else "Provider research used; web-search fallback was unavailable"
        )
        st.caption(
            f'{web_status} • '
            f'{global_meta.get("provider_candidate_count", 0)} independent market candidates • '
            f'{global_meta.get("explicit_ticker_count", 0)} directly researched tickers'
        )
        with st.expander("Global AI research scope"):
            st.write(global_meta.get("research_scope", "—"))
            fallback = global_meta.get("web_search_fallback_reason")
            if fallback:
                st.caption(f"Web-search fallback reason: {fallback}")

    st.divider()
    st.subheader("Selected Stock Research Workstation")

    analysis_symbol = st.session_state.selected_symbol
    analysis_df = st.session_state.scan_results

    if not analysis_symbol or analysis_df is None or analysis_df.empty:
        st.info("Select a ticker from the scanner to open the stock-specific research workstation. Global Ask Momo AI above remains fully available.")
    else:
        matching_rows = analysis_df[analysis_df["Symbol"] == analysis_symbol]
        if matching_rows.empty:
            st.warning("The selected ticker is no longer present in the current scan.")
        else:
            analysis_stock = matching_rows.iloc[0]
            analysis_stock_payload = normalize_stock_payload(analysis_stock)
            analysis_market = st.session_state.market_context

            with st.spinner("Loading relative strength..."):
                try:
                    analysis_rs = load_relative_strength(analysis_symbol)
                except Exception:
                    analysis_rs = {}

            comparison_options = [
                symbol
                for symbol in analysis_df["Symbol"].dropna().astype(str).tolist()
                if symbol != analysis_symbol
            ]
            compare_cols = st.columns(2)
            with compare_cols[0]:
                comparison_symbol = st.selectbox(
                    "Compare with a ticker from this scan",
                    options=["None"] + comparison_options,
                    key=f"ai_compare_{analysis_symbol}",
                )
            with compare_cols[1]:
                external_comparison_query = st.text_input(
                    "Or research any ticker/company",
                    placeholder="Example: NKE or Nike",
                    key=f"ai_external_compare_{analysis_symbol}",
                )

            comparison_payload = None
            comparison_label = "None"
            if external_comparison_query.strip():
                comparison_label = external_comparison_query.strip()
            elif comparison_symbol != "None":
                comparison_label = comparison_symbol
                comparison_rows = analysis_df[analysis_df["Symbol"] == comparison_symbol]
                if not comparison_rows.empty:
                    comparison_payload = {
                        "status": "Available",
                        "symbol": comparison_symbol,
                        "scanner_stock": comparison_rows.iloc[0].to_dict(),
                        "research_scope": "Current MomoPro scanner evidence.",
                    }

            momo_view = build_momo_engine_decision(
                analysis_stock,
                market_context=analysis_market,
                relative_strength=analysis_rs,
                smart_money_context=st.session_state.smart_money_cache.get(analysis_symbol),
                trade_intelligence_context=st.session_state.trade_intelligence_cache.get(analysis_symbol),
            )

            render_ai_summary_header(
                symbol=analysis_symbol,
                grade=analysis_stock.get("Grade", "—"),
                confidence=percent_text(analysis_stock.get("Momo Confidence")),
                momo_decision=momo_view.get("decision", "—"),
                rs_verdict=(
                    analysis_rs.get("verdict", "—")
                    if isinstance(analysis_rs, dict)
                    else "—"
                ),
            )

            report_key = (
                f"{analysis_symbol}|{comparison_label}"
                if comparison_label != "None"
                else analysis_symbol
            )

            if st.button(
                "Generate Full Independent AI Research",
                key=f"generate_ai_research_{report_key}",
                type="primary",
                width="stretch",
            ):
                try:
                    with st.spinner("Researching the full MomoPro evidence package..."):
                        news_items = load_ticker_news(analysis_symbol)
                        if not isinstance(news_items, list):
                            news_items = []
                        ranked_news = rank_news(news_items)
                        news_summary = summarize_news(ranked_news)

                        try:
                            sec_package = load_sec_filings(analysis_symbol)
                            sec_filings = (
                                sec_package.get("filings", [])
                                if isinstance(sec_package, dict)
                                else []
                            )
                        except Exception:
                            sec_filings = []

                        company_name = (
                            analysis_stock_payload.get("Company")
                            or analysis_stock_payload.get("Name")
                            or analysis_symbol
                        )
                        try:
                            fda_package = load_fda_records(company_name)
                            fda_records = (
                                fda_package.get("records", [])
                                if isinstance(fda_package, dict)
                                else []
                            )
                        except Exception:
                            fda_records = []

                        if external_comparison_query.strip():
                            comparison_payload = load_comparison_research(
                                external_comparison_query.strip()
                            )

                        smart_context = st.session_state.smart_money_cache.get(analysis_symbol)
                        trade_context = st.session_state.trade_intelligence_cache.get(analysis_symbol)

                        evidence = {
                            "symbol": analysis_symbol,
                            "stock": analysis_stock_payload,
                            "momo_engine": momo_view,
                            "market_context": analysis_market,
                            "relative_strength": analysis_rs,
                            "news_context": {
                                "summary": news_summary,
                                "articles": ranked_news[:12],
                            },
                            "sec_filings": sec_filings[:10],
                            "fda_records": fda_records[:10],
                            "smart_money_context": smart_context,
                            "trading_intelligence_context": trade_context,
                            "comparison_stock": comparison_payload,
                        }

                        report = generate_research_report(
                            api_key=_secret("OPENAI_API_KEY"),
                            symbol=analysis_symbol,
                            stock_payload=analysis_stock_payload,
                            momo_engine=momo_view,
                            market_context=analysis_market,
                            relative_strength=analysis_rs,
                            news_context=evidence["news_context"],
                            sec_filings=sec_filings[:10],
                            fda_records=fda_records[:10],
                            smart_money_context=smart_context,
                            trade_intelligence_context=trade_context,
                            comparison_payload=comparison_payload,
                        )
                        st.session_state.ai_research_reports[report_key] = report
                        st.session_state.ai_research_evidence[report_key] = evidence
                        saved_item = get_watchlist_item(analysis_symbol)
                        if saved_item is not None:
                            sync_ai_report_to_item(saved_item, report)
                            update_watchlist_item(saved_item)
                            st.success("Independent AI research completed and synced to the watchlist profile.")
                        else:
                            st.success("Independent AI research completed. Add this ticker to a watchlist to persist it there.")
                except Exception as exc:
                    st.error(f"AI research could not be generated: {exc}")

            report = st.session_state.ai_research_reports.get(report_key)
            if report:
                st.divider()
                st.subheader("Executive Summary")
                st.write(report.get("executive_summary", "—"))

                summary_cols = st.columns(3)
                summary_cols[0].metric("AI Sentiment", report.get("sentiment", "—"))
                summary_cols[1].metric("AI Confidence", f'{report.get("confidence", 0)}%')
                summary_cols[2].metric("Independent Action", report.get("independent_action", "—"))

                detail_cols = st.columns(3)
                detail_cols[0].metric("Conviction", report.get("conviction", "—"))
                detail_cols[1].metric("Risk", report.get("risk_level", "—"))
                detail_cols[2].metric("Final Rating", report.get("final_rating", "—"))

                st.markdown("### What the AI Would Do")
                st.write(report.get("action_plan", "—"))
                st.caption(f'Strategy fit: {report.get("user_strategy_fit", "—")}')

                st.markdown("### Momo Engine vs Independent AI")
                st.write(report.get("momo_engine_comparison", "—"))
                disagreement = report.get("disagreement_reason")
                if disagreement:
                    st.info(disagreement)

                analysis_tabs = st.tabs(
                    [
                        "Technical",
                        "Market",
                        "News & Catalysts",
                        "Earnings & Filings",
                        "Smart Money",
                        "Trading Intelligence",
                    ]
                )
                with analysis_tabs[0]:
                    st.write(report.get("technical_analysis", "—"))
                with analysis_tabs[1]:
                    st.write(report.get("market_analysis", "—"))
                with analysis_tabs[2]:
                    st.write(report.get("news_catalyst_analysis", "—"))
                with analysis_tabs[3]:
                    st.write(report.get("earnings_filing_analysis", "—"))
                with analysis_tabs[4]:
                    st.write(report.get("smart_money_analysis", "—"))
                with analysis_tabs[5]:
                    st.write(report.get("trading_intelligence_analysis", "—"))

                case_cols = st.columns(2)
                with case_cols[0]:
                    st.markdown("### Bull Case")
                    for item in report.get("bull_case", []):
                        st.write(f"• {item}")
                with case_cols[1]:
                    st.markdown("### Bear Case")
                    for item in report.get("bear_case", []):
                        st.write(f"• {item}")

                risk_cols = st.columns(2)
                with risk_cols[0]:
                    st.markdown("### Biggest Risks")
                    for item in report.get("biggest_risks", []):
                        st.write(f"• {item}")
                with risk_cols[1]:
                    st.markdown("### Blind Spots")
                    for item in report.get("blind_spots", []):
                        st.write(f"• {item}")

                thesis_cols = st.columns(2)
                with thesis_cols[0]:
                    st.markdown("### What Confirms the Thesis")
                    for item in report.get("confirmations", []):
                        st.write(f"• {item}")
                with thesis_cols[1]:
                    st.markdown("### What Invalidates the Thesis")
                    for item in report.get("invalidations", []):
                        st.write(f"• {item}")

                st.markdown("### AI Debate")
                debate_cols = st.columns(2)
                with debate_cols[0]:
                    st.markdown("**Bull Analyst**")
                    st.write(report.get("bull_analyst_argument", "—"))
                with debate_cols[1]:
                    st.markdown("**Bear Analyst**")
                    st.write(report.get("bear_analyst_argument", "—"))
                st.info(
                    f'Winner: {report.get("debate_winner", "—")} — '
                    f'{report.get("debate_reason", "—")}'
                )

                st.markdown("### Trade Readiness Checklist")
                checklist = report.get("readiness_checklist", [])
                if checklist:
                    st.dataframe(
                        pd.DataFrame(checklist),
                        width="stretch",
                        hide_index=True,
                    )

                st.caption(
                    f'Evidence quality: {report.get("evidence_quality", "—")}'
                )
                missing_evidence = report.get("missing_evidence", [])
                if missing_evidence:
                    with st.expander("Missing or unavailable evidence"):
                        for item in missing_evidence:
                            st.write(f"• {item}")

                with st.expander("AI Confidence Breakdown"):
                    breakdown = report.get("confidence_breakdown", [])
                    if breakdown:
                        st.dataframe(
                            pd.DataFrame(breakdown),
                            width="stretch",
                            hide_index=True,
                        )
                    else:
                        st.write("No confidence breakdown was returned.")

                questions = report.get("questions_to_ask_next", [])
                if questions:
                    st.markdown("### Suggested Follow-Up Questions")
                    for question in questions:
                        st.write(f"• {question}")
            else:
                st.info(
                    "Generate the full report to activate the independent AI opinion "
                    "and conversational research workspace."
                )

            st.divider()
            st.subheader("Ask Momo AI")
            st.caption(
                "Ask follow-up questions about the selected stock, the Momo Engine, "
                "risk, entry quality, news, Smart Money, or a comparison ticker."
            )

            chat_key = report_key
            history = st.session_state.ai_chat_history.get(chat_key, [])
            for message in history:
                with st.chat_message(message.get("role", "assistant")):
                    st.write(message.get("content", ""))

            question = st.chat_input(
                f"Ask about {analysis_symbol}...",
                key=f"ai_chat_input_{chat_key}",
            )
            if question:
                evidence = st.session_state.ai_research_evidence.get(
                    report_key,
                    {
                        "symbol": analysis_symbol,
                        "stock": analysis_stock_payload,
                        "momo_engine": momo_view,
                        "market_context": analysis_market,
                        "relative_strength": analysis_rs,
                        "smart_money_context": st.session_state.smart_money_cache.get(analysis_symbol),
                        "trading_intelligence_context": st.session_state.trade_intelligence_cache.get(analysis_symbol),
                        "comparison_stock": comparison_payload,
                    },
                )

                requested_comparison = detect_comparison_query(
                    question,
                    current_symbol=analysis_symbol,
                )
                if requested_comparison:
                    with st.spinner(f"Researching {requested_comparison} for comparison..."):
                        evidence = dict(evidence)
                        evidence["comparison_stock"] = load_comparison_research(
                            requested_comparison
                        )
                        evidence["comparison_requested_in_chat"] = requested_comparison
                        st.session_state.ai_research_evidence[report_key] = evidence

                history.append({"role": "user", "content": question})
                try:
                    with st.spinner("Momo AI is reviewing the evidence..."):
                        answer = answer_research_question(
                            api_key=_secret("OPENAI_API_KEY"),
                            symbol=analysis_symbol,
                            question=question,
                            evidence=evidence,
                            conversation=history[:-1],
                        )
                    history.append({"role": "assistant", "content": answer})
                    st.session_state.ai_chat_history[chat_key] = history
                    st.rerun()
                except Exception as exc:
                    history.append(
                        {
                            "role": "assistant",
                            "content": f"I could not answer that question: {exc}",
                        }
                    )
                    st.session_state.ai_chat_history[chat_key] = history
                    st.rerun()

            st.divider()
            st.subheader("Chart & Screenshot Analysis")
            st.caption(
                "Upload a chart or screenshot. Momo AI will analyze what is visible "
                "and combine it with the current stock evidence."
            )
            uploaded_chart = st.file_uploader(
                "Upload PNG, JPG, or JPEG",
                type=["png", "jpg", "jpeg"],
                key=f"ai_chart_upload_{analysis_symbol}",
            )
            chart_question = st.text_input(
                "What do you want Momo AI to focus on?",
                value="Analyze the entry quality, support, resistance, trend, and main risk.",
                key=f"ai_chart_question_{analysis_symbol}",
            )
            if st.button(
                "Analyze Chart / Screenshot",
                key=f"analyze_chart_{analysis_symbol}",
                width="stretch",
                disabled=uploaded_chart is None,
            ):
                try:
                    evidence = st.session_state.ai_research_evidence.get(
                        report_key,
                        {
                            "symbol": analysis_symbol,
                            "stock": analysis_stock_payload,
                            "momo_engine": momo_view,
                            "market_context": analysis_market,
                            "relative_strength": analysis_rs,
                            "smart_money_context": st.session_state.smart_money_cache.get(analysis_symbol),
                            "trading_intelligence_context": st.session_state.trade_intelligence_cache.get(analysis_symbol),
                        },
                    )
                    with st.spinner("Momo AI is analyzing the image..."):
                        st.session_state[f"ai_vision_{report_key}"] = analyze_chart_image(
                            api_key=_secret("OPENAI_API_KEY"),
                            symbol=analysis_symbol,
                            image_bytes=uploaded_chart.getvalue(),
                            mime_type=uploaded_chart.type or "image/png",
                            question=chart_question,
                            evidence=evidence,
                        )
                except Exception as exc:
                    st.error(f"Chart analysis could not be completed: {exc}")

            vision_answer = st.session_state.get(f"ai_vision_{report_key}")
            if vision_answer:
                st.markdown("### Screenshot Analysis")
                st.write(vision_answer)


# -----------------------------
# Watchlist & Alert Intelligence
# -----------------------------
if active_page_is("Watchlist"):
    st.header("Watchlist & Alert Intelligence")
    st.caption("Living stock profiles, thesis tracking, opportunity scoring, timelines, research history, and smart alerts.")

    watchlist_names = list_watchlists()
    if "active_watchlist" not in st.session_state or st.session_state.active_watchlist not in watchlist_names:
        st.session_state.active_watchlist = watchlist_names[0]

    top_left, top_mid, top_right = st.columns([2, 1, 1])
    with top_left:
        active_watchlist = st.selectbox("Watchlist", watchlist_names, index=watchlist_names.index(st.session_state.active_watchlist), key="watchlist_selector")
        st.session_state.active_watchlist = active_watchlist
    with top_mid:
        with st.popover("＋ New"):
            new_name = st.text_input("New watchlist name", key="new_watchlist_name")
            if st.button("Create watchlist", key="create_watchlist"):
                try:
                    create_watchlist(new_name); st.session_state.active_watchlist = new_name.strip(); st.rerun()
                except ValueError as exc: st.error(str(exc))
    with top_right:
        with st.popover("Manage"):
            renamed = st.text_input("Rename selected watchlist", value=active_watchlist, key="rename_watchlist_value")
            if st.button("Rename", key="rename_watchlist"):
                try: rename_watchlist(active_watchlist, renamed); st.session_state.active_watchlist=renamed.strip(); st.rerun()
                except ValueError as exc: st.error(str(exc))
            if st.button("Delete watchlist", key="delete_watchlist"):
                try: delete_watchlist(active_watchlist); st.session_state.active_watchlist=list_watchlists()[0]; st.rerun()
                except ValueError as exc: st.error(str(exc))

    symbols = get_symbols(active_watchlist)
    add_col, import_col = st.columns(2)
    with add_col:
        raw_symbols = st.text_input("Add ticker(s)", placeholder="PLTR, AMD, CVE", key="watchlist_add_symbols")
        if st.button("Add to watchlist", key="watchlist_add_button"):
            added, skipped = add_symbols(active_watchlist, [x.strip() for x in raw_symbols.replace("\n", ",").split(",") if x.strip()])
            if added: st.success("Added: " + ", ".join(added))
            if skipped: st.warning("Skipped: " + ", ".join(skipped))
            if added: st.rerun()
    with import_col:
        scan_df = st.session_state.scan_results
        available_scan_symbols = [] if scan_df is None or scan_df.empty else sorted(scan_df["Symbol"].astype(str).tolist())
        selected_imports = st.multiselect("Import from latest scanner results", available_scan_symbols, key="watchlist_scan_import")
        if st.button("Import selected", key="watchlist_import_button", disabled=not selected_imports):
            added, skipped = add_symbols(active_watchlist, selected_imports)
            if added: st.success("Imported: " + ", ".join(added)); st.rerun()

    items = [get_watchlist_item(symbol) for symbol in symbols]
    items = [item for item in items if item is not None]
    scan_lookup = {}
    if st.session_state.scan_results is not None and not st.session_state.scan_results.empty:
        scan_lookup = {str(row.get("Symbol", "")).upper(): row.to_dict() for _, row in st.session_state.scan_results.iterrows()}

    # v0.98.4: Watchlist is a view of the same symbol intelligence, not a
    # separate blank profile. Hydrate it automatically from scanner rows,
    # saved canonical analyses, metadata and any live module caches.
    watchlist_changed = False
    direct_cache = st.session_state.setdefault("direct_symbol_analysis_cache", {})
    for item in items:
        row = scan_lookup.get(item.symbol) or direct_cache.get(item.symbol) or {}
        saved_analysis = get_analysis(item.symbol)
        saved = saved_analysis.to_dict() if saved_analysis else {}
        if not row and saved:
            plan = saved.get("plan") or {}
            technicals = saved.get("technicals") or {}
            row = {
                "Symbol": item.symbol,
                "Company": (saved.get("identity") or {}).get("company"),
                "Sector": (saved.get("identity") or {}).get("sector"),
                "Industry": (saved.get("identity") or {}).get("industry"),
                "Close": technicals.get("close") or technicals.get("price"),
                "Grade": saved.get("grade"),
                "Momo Score": saved.get("momo_score"),
                "Momo Confidence": saved.get("momo_confidence"),
                "Setup": saved.get("setup"),
                "Reference Entry": plan.get("reference_entry"),
                "Risk Reference": plan.get("stop"),
                "T1": plan.get("t1"), "T2": plan.get("t2"), "T3": plan.get("t3"),
                "T1 R": plan.get("t1_r"), "T2 R": plan.get("t2_r"), "T3 R": plan.get("t3_r"),
            }
        metadata = get_company_metadata(
            item.symbol,
            fmp_api_key=_secret("FMP_API_KEY"),
            alpha_vantage_api_key=_secret("ALPHA_VANTAGE_API_KEY"),
        )
        row = dict(row or {})
        row.update({
            "Symbol": item.symbol,
            "Company": row.get("Company") or metadata.get("company"),
            "Sector": row.get("Sector") or metadata.get("sector"),
            "Industry": row.get("Industry") or metadata.get("industry"),
        })
        report = st.session_state.ai_research_reports.get(item.symbol)
        if report is None:
            report = next((value for key, value in st.session_state.ai_research_reports.items() if str(key).split("|", 1)[0] == item.symbol), None)
        smart_context = st.session_state.smart_money_cache.get(item.symbol) or saved.get("smart_money_context")
        trade_context = st.session_state.trade_intelligence_cache.get(item.symbol) or saved.get("trading_intelligence")
        market_context = saved.get("market_context") or st.session_state.market_context
        before = item.to_dict()
        refresh_item_from_scan(
            item, row, ai_report=report, market_context=market_context,
            smart_money_context=smart_context, trade_intelligence_context=trade_context,
        )
        if item.to_dict() != before:
            update_watchlist_item(item)
            watchlist_changed = True

    def _refresh_one_watchlist_item(item, *, force_metadata: bool = False) -> None:
        """Load one living profile from the same canonical pipeline used by Stock Report."""
        row = scan_lookup.get(item.symbol) or direct_cache.get(item.symbol)
        if not row:
            row = analyze_symbol(
                st.secrets["ALPACA_API_KEY"],
                st.secrets["ALPACA_SECRET_KEY"],
                item.symbol,
            )
            direct_cache[item.symbol] = row
        row = normalize_stock_payload(row)
        metadata = get_company_metadata(
            item.symbol,
            fmp_api_key=_secret("FMP_API_KEY"),
            alpha_vantage_api_key=_secret("ALPHA_VANTAGE_API_KEY"),
            force_refresh=force_metadata,
        )
        row.update({
            "Symbol": item.symbol,
            "Company": row.get("Company") or metadata.get("company"),
            "Sector": row.get("Sector") or metadata.get("sector"),
            "Industry": row.get("Industry") or metadata.get("industry"),
            "Market Cap": row.get("Market Cap") or metadata.get("market_cap"),
            "Float": row.get("Float") or metadata.get("float_shares"),
            "Shares Outstanding": row.get("Shares Outstanding") or metadata.get("shares_outstanding"),
        })
        report = st.session_state.ai_research_reports.get(item.symbol)
        if report is None:
            report = next((value for key, value in st.session_state.ai_research_reports.items() if str(key).split("|", 1)[0] == item.symbol), None)
        existing_intelligence = item.intelligence or {}
        relative_context = existing_intelligence.get("relative_strength")
        smart_context = (
            st.session_state.smart_money_cache.get(item.symbol)
            or existing_intelligence.get("smart_money")
        )
        trade_context = (
            st.session_state.trade_intelligence_cache.get(item.symbol)
            or existing_intelligence.get("trading_intelligence")
        )

        # Each provider is isolated. One unavailable module must never prevent
        # the other watchlist snapshots from loading and being saved.
        try:
            relative_context = get_relative_strength(
                st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_SECRET_KEY"], item.symbol
            )
        except Exception:
            pass
        try:
            smart_context = get_smart_money_intelligence(
                item.symbol,
                st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_SECRET_KEY"],
                _secret("ALPHA_VANTAGE_API_KEY"), _secret("FINNHUB_API_KEY"), _secret("FMP_API_KEY"),
            )
        except Exception:
            pass
        try:
            trade_context = get_trade_intelligence(
                st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_SECRET_KEY"], item.symbol, row
            )
        except Exception:
            pass

        if smart_context:
            st.session_state.smart_money_cache[item.symbol] = smart_context
        if trade_context:
            st.session_state.trade_intelligence_cache[item.symbol] = trade_context
        refresh_item_from_scan(
            item, row, ai_report=report,
            market_context=st.session_state.market_context,
            smart_money_context=smart_context,
            trade_intelligence_context=trade_context,
            relative_strength_context=relative_context,
        )
        update_watchlist_item(item)

    # Automatic watchlist hydration. Saved values render immediately; missing
    # non-AI modules are filled once per session without requiring a button.
    auto_refresh_state = st.session_state.setdefault("watchlist_auto_refresh_state", {})
    missing_items = []
    for item in items:
        intelligence = item.intelligence or {}
        technical = item.technical or {}
        missing_core = not technical or any(
            not intelligence.get(key)
            for key in ("relative_strength", "smart_money", "trading_intelligence", "market_context")
        )
        if missing_core and not auto_refresh_state.get(item.symbol):
            missing_items.append(item)

    if missing_items:
        completed = 0
        failures = []
        with st.spinner("Loading saved watchlist intelligence and filling missing modules..."):
            for item in missing_items[:5]:
                auto_refresh_state[item.symbol] = True
                try:
                    _refresh_one_watchlist_item(item, force_metadata=False)
                    completed += 1
                except Exception as exc:
                    failures.append(item.symbol)
                    auto_refresh_state.pop(item.symbol, None)
        if completed:
            st.rerun()
        elif failures:
            st.warning(
                "Watchlist data could not be loaded for: " + ", ".join(failures) +
                ". Use Refresh Watchlist Data to retry."
            )

    action_cols = st.columns([1, 1, 2])
    if action_cols[0].button("Refresh Watchlist Data", key="refresh_watchlist_intelligence", disabled=not items):
        refreshed = 0
        failed: list[str] = []
        with st.spinner("Refreshing watchlist profiles from the shared symbol pipeline..."):
            for item in items:
                try:
                    _refresh_one_watchlist_item(item, force_metadata=True)
                    auto_refresh_state[item.symbol] = True
                    refreshed += 1
                except Exception:
                    failed.append(item.symbol)
                    auto_refresh_state.pop(item.symbol, None)
        if failed:
            st.warning(f"Refreshed {refreshed} profile(s). Could not fully refresh: {', '.join(failed)}.")
        else:
            st.success(f"Refreshed all {refreshed} watchlist profile(s).")
        st.rerun()
    if action_cols[1].button("Evaluate Alerts", key="evaluate_watchlist_alerts", disabled=not items):
        fired = evaluate_alerts({item.symbol: item for item in items})
        for item in items:
            update_watchlist_item(item)
        st.success(f"{len(fired)} alert(s) triggered.") if fired else st.info("No alert conditions are currently met.")
        st.rerun()
    action_cols[2].caption("Saved values display immediately. Missing non-AI modules load automatically; Refresh Watchlist Data is the force-refresh control.")

    brief = build_morning_brief(items)
    st.subheader("☀️ Morning Brief")
    brief_cols = st.columns(5)
    brief_cols[0].metric("Watchlist Stocks", brief["count"])
    brief_cols[1].metric("Thesis Improved", brief["improved"])
    brief_cols[2].metric("Weakened / Invalid", brief["weakened"])
    brief_cols[3].metric("Highest Opportunity", brief["top_symbol"] or "—")
    brief_cols[4].metric("Opportunity Score", brief["top_opportunity"] if brief["top_opportunity"] is not None else "—")

    if brief["ranked"]:
        priority_rows = []
        for rank, item in enumerate(brief["ranked"], 1):
            ai_confidence = item.ai_state.get("ai_confidence")
            opportunity = item.ai_state.get("opportunity_score")
            priority_rows.append({"Priority": rank, "Symbol": item.symbol, "Grade": str(item.technical.get("grade") or "—"), "AI Confidence": "—" if ai_confidence is None else f"{float(ai_confidence):.0f}%", "Opportunity": "—" if opportunity is None else f"{float(opportunity):.0f}", "AI Status": str(item.ai_state.get("thesis_status") or "Not evaluated"), "Why Now": str(item.ai_state.get("opportunity_reason") or "Run refresh intelligence.")})
        st.dataframe(pd.DataFrame(priority_rows), hide_index=True, width="stretch")

    profile_tab, alerts_tab, history_tab = st.tabs(["Smart Watchlist", "Smart Alerts", "Alert Inbox"])
    with profile_tab:
        if not symbols:
            st.info("Add a ticker or import one from the scanner to create its living profile.")
        else:
            selected_symbol = st.selectbox("Open living profile", symbols, key="watchlist_profile_symbol")
            item = get_watchlist_item(selected_symbol) or WatchlistItem(symbol=selected_symbol)
            tech, ai = item.technical or {}, item.ai_state or {}
            header_cols = st.columns(6)
            header_cols[0].metric("Symbol", item.symbol)
            header_cols[1].metric("Grade", tech.get("grade", "—"))
            header_cols[2].metric("Momo Score", tech.get("momo_score", "—"))
            header_cols[3].metric("AI Confidence", ai.get("ai_confidence", "—"))
            header_cols[4].metric("Opportunity", ai.get("opportunity_score", "—"))
            header_cols[5].metric("Price", money_text(tech.get("price")))
            st.caption(ai.get("opportunity_reason", "Run Refresh Intelligence after a scanner run to calculate Opportunity Score."))

            identity_tab, thesis_tab, timeline_tab, research_tab = st.tabs(["Profile", "AI Thesis Tracker", "Timeline", "Research History"])
            with identity_tab:
                st.caption("Company identity and system snapshots fill automatically during Refresh Intelligence. Tags are personal and editable.")
                c1, c2 = st.columns(2)
                item.company = c1.text_input("Company", value=item.company, key=f"company_{item.symbol}")
                item.sector = c2.text_input("Sector", value=item.sector, key=f"sector_{item.symbol}")
                item.industry = c1.text_input("Industry", value=item.industry, key=f"industry_{item.symbol}")
                tags_text = c2.text_input("Tags", value=", ".join(item.tags), key=f"tags_{item.symbol}")
                item.tags = [x.strip() for x in tags_text.split(",") if x.strip()]
                st.markdown("#### Technical Snapshot")
                if tech:
                    tech_cols = st.columns(5)
                    tech_cols[0].metric("Price", money_text(tech.get("price")))
                    tech_cols[1].metric("Grade", tech.get("grade") or "—")
                    tech_cols[2].metric("Momo Score", tech.get("momo_score") if tech.get("momo_score") is not None else "—")
                    tech_cols[3].metric("RSI", tech.get("rsi") if tech.get("rsi") is not None else "—")
                    tech_cols[4].metric("RVOL", tech.get("rvol") if tech.get("rvol") is not None else "—")
                    st.caption(f"Setup: {tech.get('setup') or '—'} · ATR: {tech.get('atr_pct') if tech.get('atr_pct') is not None else '—'}% · Distance from EMA21: {tech.get('distance_ema21_pct') if tech.get('distance_ema21_pct') is not None else '—'}%")
                else:
                    st.info("Technical data has not been loaded for this ticker. Click Refresh Watchlist Data above.")

                st.markdown("#### Independent AI Snapshot")
                independent_ai = (item.intelligence or {}).get("independent_ai", {})
                if independent_ai.get("status") == "Available":
                    ai_cols = st.columns(3)
                    ai_cols[0].metric("AI Confidence", independent_ai.get("confidence", "—"))
                    ai_cols[1].metric("AI Sentiment", independent_ai.get("sentiment", "—"))
                    ai_cols[2].metric("Independent Action", independent_ai.get("independent_action", "—"))
                    st.write(independent_ai.get("executive_summary") or "No executive summary was saved.")
                else:
                    st.info("Independent AI Research is intentionally separate and has not been generated yet. Use AI Analysis → Generate Full Independent AI Research for this ticker.")

                st.markdown("#### Intelligence Snapshot")
                intelligence = item.intelligence or {}
                intel_cols = st.columns(4)
                relative = intelligence.get("relative_strength") or {}
                smart = intelligence.get("smart_money") or {}
                trading = intelligence.get("trading_intelligence") or {}
                market = intelligence.get("market_context") or {}
                intel_cols[0].metric("Relative Strength", relative.get("verdict") or relative.get("score") or "Not loaded")
                intel_cols[1].metric("Smart Money", smart.get("verdict") or smart.get("overall_score") or "Not loaded")
                intel_cols[2].metric("Trading Intelligence", trading.get("status") or trading.get("overall_score") or "Not loaded")
                intel_cols[3].metric("Market Regime", market.get("market_regime") or market.get("regime") or "Not loaded")
                if not any((relative, smart, trading, market)):
                    st.info("No intelligence modules are saved yet. Click Refresh Watchlist Data above.")
                if st.button("Save profile", key=f"save_profile_{item.symbol}"):
                    update_watchlist_item(item); st.success("Profile saved.")

            with thesis_tab:
                st.caption("These are your personal planning fields. MomoPro will evaluate them, but will not overwrite them.")
                item.thesis = st.text_area("Why did you save this stock?", value=item.thesis, height=100, key=f"thesis_{item.symbol}")
                p1, p2, p3 = st.columns(3)
                item.entry_idea = p1.text_input("Entry idea", value=item.entry_idea, key=f"entry_{item.symbol}")
                item.stop = p2.number_input("Stop", min_value=0.0, value=float(item.stop or 0), step=0.01, key=f"stop_{item.symbol}") or None
                item.target = p3.number_input("Target", min_value=0.0, value=float(item.target or 0), step=0.01, key=f"target_{item.symbol}") or None
                item.notes = st.text_area("Notes", value=item.notes, key=f"notes_{item.symbol}")
                st.info(f"AI Status: {ai.get('thesis_status', 'Not evaluated')} · Recommendation: {ai.get('recommendation', 'Not evaluated')}")
                if st.button("Save thesis", key=f"save_thesis_{item.symbol}"):
                    item.timeline.append({"timestamp": utc_now(), "event": "Thesis updated", "details": item.thesis})
                    update_watchlist_item(item); st.success("Thesis saved.")

            with timeline_tab:
                manual_event = st.text_input("Add timeline event", placeholder="Earnings date moved / Sold / New catalyst", key=f"manual_event_{item.symbol}")
                if st.button("Add event", key=f"add_event_{item.symbol}") and manual_event.strip():
                    item.timeline.append({"timestamp": utc_now(), "event": manual_event.strip(), "details": "Manual event"}); update_watchlist_item(item); st.rerun()
                if item.timeline:
                    for event in reversed(item.timeline):
                        st.markdown(
                            f"**{event.get('event', 'Event')}**  \n"
                            f"{event.get('details', '')}  \n"
                            f"<small>{event.get('timestamp', '')}</small>",
                            unsafe_allow_html=True,
                        )
                        st.divider()
                else: st.caption("No timeline events yet.")

            with research_tab:
                research_title = st.text_input("Snapshot title", placeholder="Pre-earnings research", key=f"research_title_{item.symbol}")
                research_body = st.text_area("Save an AI report, conclusion, or research note", height=180, key=f"research_body_{item.symbol}")
                if st.button("Save research snapshot", key=f"save_research_{item.symbol}") and research_body.strip():
                    item.research_snapshots.append({"timestamp": utc_now(), "title": research_title.strip() or "Research snapshot", "content": research_body.strip(), "ai_state": dict(item.ai_state), "technical": dict(item.technical)})
                    item.timeline.append({"timestamp": utc_now(), "event": "Research snapshot saved", "details": research_title.strip() or "Research snapshot"}); update_watchlist_item(item); st.rerun()
                for snap in reversed(item.research_snapshots):
                    with st.expander(f"{snap.get('title','Research')} · {snap.get('timestamp','')}"):
                        st.write(snap.get("content", "")); st.caption(f"Opportunity then: {snap.get('ai_state',{}).get('opportunity_score','—')} · AI Confidence then: {snap.get('ai_confidence', snap.get('ai_state',{}).get('ai_confidence','—'))}")

            quick = st.columns(6)
            if quick[0].button("Open Stock Report", key=f"quick_report_{item.symbol}"):
                navigate_to("Scanner", symbol=item.symbol)
            if quick[1].button("Trade Planner", key=f"quick_plan_{item.symbol}"):
                st.session_state.trade_plan_prefill = {"symbol": item.symbol, "entry": item.entry_idea or tech.get("price"), "stop": item.stop, "t1": item.target}
                navigate_to("Trade Planner", symbol=item.symbol)
            if quick[2].button("Journal", key=f"quick_journal_{item.symbol}"):
                st.session_state.journal_prefill = {"symbol": item.symbol, "entry_price": tech.get("price") or 0, "initial_stop": item.stop or 0, "t1": item.target or 0, "thesis": item.thesis}
                navigate_to("Journal", symbol=item.symbol)
            if quick[3].button("AI Research", key=f"quick_ai_{item.symbol}"):
                navigate_to("AI Analysis", symbol=item.symbol)
            if quick[4].button("News", key=f"quick_news_{item.symbol}"):
                navigate_to("News", symbol=item.symbol)
            if quick[5].button("Remove", key=f"quick_remove_{item.symbol}"):
                remove_symbol(active_watchlist, item.symbol); st.rerun()

    with alerts_tab:
        st.subheader("Create Smart Alert")
        if not symbols: st.info("Add watchlist symbols before creating alerts.")
        else:
            rule_labels = list(RULE_TYPES.keys())
            alert_name = st.text_input("Alert name", key="new_alert_name")
            alert_symbols = st.multiselect("Apply to", symbols, default=symbols[:1], key="new_alert_symbols")
            rule_label = st.selectbox("Condition", rule_labels, key="new_alert_rule_type")
            rule_type = RULE_TYPES[rule_label]
            if rule_type in {"grade_equals", "setup_contains", "thesis_equals", "recommendation_equals"}:
                alert_value = st.text_input("Value", key="new_alert_text_value")
            else:
                alert_value = st.number_input("Threshold", value=0.0, step=0.1, key="new_alert_number_value")
            cooldown = st.number_input("Cooldown hours", min_value=1, value=24, step=1, key="new_alert_cooldown")
            if st.button("Create alert", key="create_smart_alert", disabled=not alert_symbols):
                create_rule(alert_name or rule_label, alert_symbols, rule_type, alert_value, cooldown); st.success("Alert created."); st.rerun()

        alert_data = load_alerts()
        st.markdown("#### Active Rules")
        for rule in alert_data["rules"]:
            cols = st.columns([3, 2, 1, 1])
            cols[0].write(f"**{rule['name']}**  \n{', '.join(rule['symbols'])}")
            cols[1].write(f"{rule['type']} · {rule['value']}")
            if cols[2].button("Pause" if rule.get("enabled", True) else "Resume", key=f"toggle_alert_{rule['id']}"):
                set_rule_enabled(rule["id"], not rule.get("enabled", True)); st.rerun()
            if cols[3].button("Delete", key=f"delete_alert_{rule['id']}"):
                delete_rule(rule["id"]); st.rerun()

    with history_tab:
        alert_data = load_alerts(); unread = sum(not e.get("read", False) for e in alert_data["events"])
        h1, h2, h3 = st.columns([2, 1, 1]); h1.metric("Unread Alerts", unread)
        if h2.button("Mark all read", key="mark_all_alerts_read"): mark_event_read(); st.rerun()
        if h3.button("Clear history", key="clear_alert_history"): clear_events(); st.rerun()
        if not alert_data["events"]: st.info("No alerts have triggered yet.")
        for event in alert_data["events"]:
            with st.expander(f"{'🔔' if not event.get('read') else '✓'} {event['symbol']} · {event['rule_name']} · {event['timestamp']}"):
                st.write(event.get("details", ""))
                if not event.get("read") and st.button("Mark read", key=f"read_alert_{event['id']}"):
                    mark_event_read(event["id"]); st.rerun()


# -----------------------------
# Trade Planner
# -----------------------------
if active_page_is("Trade Planner"):
    st.header("Trade Planner")
    st.caption("Review the official canonical plan, then customize position sizing or personal execution notes without changing the engine plan.")

    prefill = st.session_state.trade_plan_prefill or {}
    desired_planner_symbol = str(prefill.get("symbol") or st.session_state.get("selected_symbol") or "").upper().strip()
    if "planner_symbol" not in st.session_state:
        st.session_state.planner_symbol = desired_planner_symbol
    planner_symbol = st.text_input(
        "Ticker", key="planner_symbol", on_change=sync_symbol_widget, args=("planner_symbol",)
    ).upper().strip()
    canonical_saved = st.session_state.canonical_analysis_cache.get(planner_symbol) or (get_analysis(planner_symbol).to_dict() if planner_symbol and get_analysis(planner_symbol) else None)
    if canonical_saved:
        saved_plan = canonical_saved.get("plan", {})
        st.info(
            f"Official plan loaded for {planner_symbol}: Entry {money_text(saved_plan.get('reference_entry'))}, "
            f"Stop {money_text(saved_plan.get('stop'))}, T1 {money_text(saved_plan.get('t1'))}, "
            f"T2 {money_text(saved_plan.get('t2'))}, T3 {money_text(saved_plan.get('t3'))}."
        )
    planner_account_default, planner_account_source = get_effective_account_size(
        st.session_state.momopro_settings
    )
    if "planner_account_size" not in st.session_state:
        st.session_state.planner_account_size = planner_account_default
    elif not st.session_state.get("planner_account_size_user_override", False):
        st.session_state.planner_account_size = planner_account_default

    account_size = st.number_input(
        "Account Size ($)",
        min_value=0.0,
        step=500.0,
        key="planner_account_size",
        help=(
            "Automatically uses connected Webull buying power/cash when available. "
            "You may still enter a manual planning amount."
        ),
        on_change=lambda: st.session_state.__setitem__("planner_account_size_user_override", True),
    )
    if planner_account_source != "Manual fallback":
        st.caption(f"Automatic planning balance: {money_text(planner_account_default)} · {planner_account_source}")
    else:
        st.caption("Webull account value is unavailable; using the manual risk-setting fallback.")

    risk_pct = st.number_input(
        "Risk Per Trade (%)",
        min_value=0.0,
        max_value=100.0,
        value=float(get_setting("risk.risk_per_trade_pct", 1.0, st.session_state.momopro_settings)),
        step=0.1,
        format="%.2f",
        key="planner_risk_pct",
        help=(
            "Type any value from 0% to 100%. Press Enter or click outside "
            "the field to apply it."
        ),
    )

    direction = st.radio(
        "Trade Direction", ["Long", "Short"], horizontal=True,
        index=1 if str(prefill.get("direction") or "Long").title() == "Short" else 0,
        key="planner_direction",
    )
    plan_cols = st.columns(5)
    entry = plan_cols[0].number_input("Entry", min_value=0.0, value=float(prefill.get("entry") or 0.0), step=0.01)
    stop = plan_cols[1].number_input("Stop", min_value=0.0, value=float(prefill.get("stop") or 0.0), step=0.01)
    t1 = plan_cols[2].number_input("T1", min_value=0.0, value=float(prefill.get("t1") or 0.0), step=0.01)
    t2 = plan_cols[3].number_input("T2", min_value=0.0, value=float(prefill.get("t2") or 0.0), step=0.01)
    t3 = plan_cols[4].number_input("T3", min_value=0.0, value=float(prefill.get("t3") or 0.0), step=0.01)

    sizing = calculate_position_size(
        account_size=account_size,
        risk_percent=risk_pct,
        entry_price=entry,
        stop_price=stop,
        direction=direction,
    )

    risk_dollars = sizing["risk_budget"]
    risk_per_share = sizing["risk_per_share"]
    risk_based_shares = sizing["risk_based_shares"]
    cash_based_shares = sizing["cash_based_shares"]
    shares = sizing["final_shares"]
    position_value = sizing["position_value"]
    total_dollar_risk = sizing["total_dollar_risk"]
    unused_cash = sizing["unused_cash"]
    unused_risk_budget = sizing["unused_risk_budget"]
    sizing_limit = sizing["sizing_constraint"]

    st.caption("Position Sizing Engine v0.5.3 — cash cap and stop-risk cap are both enforced.")

    result_cols = st.columns(4)
    result_cols[0].metric("Risk Budget", money_text(risk_dollars))
    result_cols[1].metric("Risk / Share", money_text(risk_per_share))
    result_cols[2].metric("Final Position Size", f"{shares:,} shares" if shares else "—")
    result_cols[3].metric("Position Value", money_text(position_value) if shares else "—")

    detail_cols = st.columns(4)
    detail_cols[0].metric(
        "Total Dollar Risk",
        money_text(total_dollar_risk) if shares else "—",
    )
    detail_cols[1].metric(
        "Cash-Limit Shares",
        f"{cash_based_shares:,}" if cash_based_shares else "—",
    )
    detail_cols[2].metric(
        "Risk-Limit Shares",
        f"{risk_based_shares:,}" if risk_based_shares else "—",
    )
    detail_cols[3].metric("Sizing Constraint", sizing_limit)

    extra_cols = st.columns(2)
    extra_cols[0].metric(
        "Unused Cash",
        money_text(unused_cash) if account_size > 0 else "—",
    )
    extra_cols[1].metric(
        "Unused Risk Budget",
        money_text(unused_risk_budget) if shares else "—",
    )

    if shares > 0 and sizing_limit == "Cash-Limited":
        st.info(
            "Cash-Limited: available account cash allows fewer shares than the "
            "selected stop-risk budget. Position value is capped at account size."
        )
    elif shares > 0 and sizing_limit == "Risk-Limited":
        st.info(
            "Risk-Limited: the selected dollar-risk budget allows fewer shares "
            "than the account cash could purchase."
        )
    elif shares > 0 and sizing_limit == "Cash and Risk Limits Match":
        st.info("Cash and risk limits produce the same final share count.")
    elif sizing["error"]:
        st.warning(sizing["error"])

    rr_rows = []
    for name, target in [("T1", t1), ("T2", t2), ("T3", t3)]:
        if direction == "Short":
            reward = entry - target if entry > target > 0 else None
        else:
            reward = target - entry if target > entry > 0 else None
        r_multiple = reward / risk_per_share if reward is not None and risk_per_share and risk_per_share > 0 else None
        dollar_profit = reward * shares if reward is not None and shares > 0 else None
        return_pct = (reward / entry) * 100 if reward is not None and entry > 0 else None
        rr_rows.append({
            "Target": name,
            "Price": target if target > 0 else None,
            "Reward / Share": round(reward, 2) if reward is not None else None,
            "Dollar Profit": round(dollar_profit, 2) if dollar_profit is not None else None,
            "Return %": round(return_pct, 2) if return_pct is not None else None,
            "R Multiple": round(r_multiple, 2) if r_multiple is not None else None,
        })
    st.dataframe(pd.DataFrame(rr_rows), width="stretch", hide_index=True)

    st.markdown("### Plan Notes")
    plan_notes = st.text_area("Trade Thesis / Confirmation / Invalidation", key="trade_plan_notes")
    planner_action_1, planner_action_2 = st.columns(2)
    if planner_action_1.button("Save Plan to Session", width="stretch"):
        st.session_state.trade_plan_prefill = {"symbol": planner_symbol, "direction": direction, "entry": entry, "stop": stop, "t1": t1, "t2": t2, "t3": t3, "notes": plan_notes}
        st.success("Trade plan saved in this session.")
    if planner_action_2.button("Send Plan to Journal", width="stretch"):
        plan_id = f"MP-{planner_symbol}-{uuid4().hex[:10].upper()}"
        plan_created_at = utc_now()
        plan_snapshot = {"symbol": planner_symbol, "direction": direction, "entry": entry, "stop": stop, "t1": t1, "t2": t2, "t3": t3, "shares": shares, "thesis": plan_notes, "created_at": plan_created_at}
        st.session_state.journal_prefill = {
            "symbol": planner_symbol, "entry_price": entry, "shares": shares,
            "initial_stop": stop, "t1": t1, "t2": t2, "t3": t3,
            "thesis": plan_notes, "plan_id": plan_id, "plan_created_at": plan_created_at,
            "plan_snapshot": plan_snapshot, "plan_completeness": 100.0 if all([planner_symbol, entry, stop, t1, shares]) else 65.0,
            "source": "momopro_plan",
        }
        st.success("Trade plan loaded into the Journal. Open the Journal tab to review and save it.")


# -----------------------------
# Journal & Open Trades
# -----------------------------
if active_page_is("Journal"):
    st.header("Journal & Open Trades")
    st.caption("Plan, monitor, manage, close, and review every trade in one persistent record.")

    journal_trades = load_trades()
    journal_open = [trade for trade in journal_trades if trade.status in {"open", "partial"}]
    journal_closed = [trade for trade in journal_trades if trade.status == "closed"]

    metric_cols = st.columns(4)
    metric_cols[0].metric("Open Trades", len(journal_open))
    metric_cols[1].metric("Closed Trades", len(journal_closed))
    metric_cols[2].metric("Partial Positions", sum(trade.status == "partial" for trade in journal_open))
    metric_cols[3].metric("Total Journal Records", len(journal_trades))

    open_tab, new_tab, manage_tab, closed_tab, broker_tab = st.tabs(
        ["Open Trades", "New Trade", "Manage Trade", "Closed Trades & Review", "Broker Import & Reconcile"]
    )

    with open_tab:
        st.subheader("Open Positions")
        if not journal_open:
            st.info("No open trades yet. Create one manually or send a plan from the Trade Planner.")
        else:
            open_rows = [trade_summary(trade) for trade in journal_open]
            st.dataframe(pd.DataFrame(open_rows), width="stretch", hide_index=True)
            for trade in journal_open:
                with st.expander(f"{trade.symbol} · {trade.status.title()} · {trade.remaining_shares:g} shares remaining"):
                    summary_cols = st.columns(5)
                    summary_cols[0].metric("Entry", money_text(trade.entry_price))
                    summary_cols[1].metric("Current Stop", money_text(trade.current_stop))
                    summary_cols[2].metric("T1", money_text(trade.t1))
                    summary_cols[3].metric("Momo Score", trade.momo_score if trade.momo_score is not None else "—")
                    summary_cols[4].metric("AI Confidence", f"{trade.ai_confidence:.0f}%" if trade.ai_confidence is not None else "—")
                    st.markdown(f"**Setup:** {trade.setup or '—'}  |  **Grade:** {trade.grade or '—'}  |  **Dee Fit:** {trade.dee_fit or '—'}")
                    if trade.thesis:
                        st.markdown("**Entry Thesis**")
                        st.write(trade.thesis)
                    if trade.updates:
                        st.markdown("**Latest Management Updates**")
                        for update in trade.updates[:5]:
                            st.caption(f"{update.date} · {update.update_type}")
                            st.write(update.note or "No note entered.")
                    if trade.exits:
                        st.markdown("**Partial Exits**")
                        st.dataframe(pd.DataFrame([{"Date": item.date, "Shares": item.shares, "Price": item.price, "Reason": item.reason} for item in trade.exits]), width="stretch", hide_index=True)

    with new_tab:
        st.subheader("Create Trade Record")
        prefill = st.session_state.journal_prefill or {}
        scan_df = st.session_state.scan_results
        scanner_row = None
        default_symbol = str(prefill.get("symbol", "")).upper()
        if default_symbol and scan_df is not None and not scan_df.empty and "Symbol" in scan_df.columns:
            matched = scan_df[scan_df["Symbol"].astype(str).str.upper() == default_symbol]
            if not matched.empty:
                scanner_row = matched.iloc[0]

        def journal_scan_value(names, default=None):
            if scanner_row is None:
                return default
            for name in names:
                if name in scanner_row.index and valid_value(scanner_row.get(name)):
                    return scanner_row.get(name)
            return default

        ai_report = None
        if default_symbol:
            matching_reports = [report for key, report in st.session_state.ai_research_reports.items() if str((report or {}).get("symbol") or key).upper().startswith(default_symbol)]
            if matching_reports:
                ai_report = matching_reports[-1]

        base_1, base_2, base_3, base_4 = st.columns(4)
        journal_symbol = base_1.text_input("Ticker", value=default_symbol, key="journal_new_symbol").upper().strip()
        journal_direction = base_2.selectbox("Direction", ["long", "short"], key="journal_new_direction")
        journal_entry_date = base_3.date_input("Entry Date", key="journal_new_entry_date")
        journal_status = base_4.selectbox("Starting Status", ["open"], key="journal_new_status")

        price_1, price_2, price_3, price_4 = st.columns(4)
        journal_entry = price_1.number_input("Entry Price", min_value=0.0, value=float(prefill.get("entry_price") or 0.0), step=0.01, key="journal_new_entry")
        journal_shares = price_2.number_input("Shares", min_value=0.0, value=float(prefill.get("shares") or 0.0), step=1.0, key="journal_new_shares")
        journal_stop = price_3.number_input("Initial Stop", min_value=0.0, value=float(prefill.get("initial_stop") or 0.0), step=0.01, key="journal_new_stop")
        journal_setup = price_4.text_input("Setup", value=str(journal_scan_value(["Setup", "Setup Tag"], "")), key="journal_new_setup")

        target_1, target_2, target_3 = st.columns(3)
        journal_t1 = target_1.number_input("T1", min_value=0.0, value=float(prefill.get("t1") or 0.0), step=0.01, key="journal_new_t1")
        journal_t2 = target_2.number_input("T2", min_value=0.0, value=float(prefill.get("t2") or 0.0), step=0.01, key="journal_new_t2")
        journal_t3 = target_3.number_input("T3", min_value=0.0, value=float(prefill.get("t3") or 0.0), step=0.01, key="journal_new_t3")

        intelligence_1, intelligence_2, intelligence_3, intelligence_4 = st.columns(4)
        journal_grade = intelligence_1.text_input("Grade", value=str(journal_scan_value(["Grade"], "")), key="journal_new_grade")
        journal_momo = intelligence_2.number_input("Momo Score", min_value=0.0, max_value=100.0, value=float(journal_scan_value(["Momo Score", "Score"], 0.0) or 0.0), key="journal_new_momo")
        journal_opportunity = intelligence_3.number_input("Opportunity Score", min_value=0.0, max_value=100.0, value=float(journal_scan_value(["Opportunity Score", "Opportunity"], 0.0) or 0.0), key="journal_new_opportunity")
        journal_ai_confidence = intelligence_4.number_input("Independent AI Confidence", min_value=0.0, max_value=100.0, value=float((ai_report or {}).get("confidence") or 0.0), key="journal_new_ai_confidence")

        journal_dee_fit = st.text_input("Dee Fit", value=str(journal_scan_value(["Dee Fit"], "")), key="journal_new_dee_fit")
        journal_thesis = st.text_area("Entry Thesis / Why This Trade", value=str(prefill.get("thesis") or ""), key="journal_new_thesis")
        confirm_col, invalid_col = st.columns(2)
        journal_confirmation = confirm_col.text_area("Required Confirmation", key="journal_new_confirmation")
        journal_invalidation = invalid_col.text_area("Thesis Invalidation", key="journal_new_invalidation")

        context_col_1, context_col_2 = st.columns(2)
        journal_market = context_col_1.text_area("Market / Sector Context", value=str((st.session_state.market_context or {}).get("summary") or ""), key="journal_new_market")
        journal_news = context_col_2.text_area("News / Catalyst Context", key="journal_new_news")
        journal_smart_money = st.text_area("Smart Money Context", key="journal_new_smart_money")
        journal_notes = st.text_area("Personal Notes", key="journal_new_notes")
        journal_image = st.file_uploader("Chart Screenshot (optional)", type=["png", "jpg", "jpeg", "webp"], key="journal_new_image")

        if st.button("Save Trade to Journal", type="primary", width="stretch", key="journal_create_trade"):
            try:
                created = create_trade(
                    symbol=journal_symbol, status=journal_status, direction=journal_direction,
                    entry_date=f"{journal_entry_date.isoformat()}T00:00:00+00:00",
                    entry_price=journal_entry, shares=journal_shares,
                    initial_stop=journal_stop or None, t1=journal_t1 or None, t2=journal_t2 or None, t3=journal_t3 or None,
                    setup=journal_setup, grade=journal_grade, momo_score=journal_momo or None,
                    dee_fit=journal_dee_fit, opportunity_score=journal_opportunity or None,
                    ai_confidence=journal_ai_confidence or None,
                    ai_action=str((ai_report or {}).get("independent_action") or ""),
                    market_regime=journal_market, news_context=journal_news,
                    smart_money_context=journal_smart_money, thesis=journal_thesis,
                    confirmation=journal_confirmation, invalidation=journal_invalidation, notes=journal_notes,
                )
                if journal_image is not None:
                    attachment_path = save_attachment(created.id, journal_image)
                    if attachment_path:
                        update_trade(created.id, screenshot_paths=[attachment_path])
                st.session_state.journal_prefill = {}
                st.success(f"{created.symbol} was saved as an open trade.")
                st.rerun()
            except Exception as error:
                st.error(str(error))

    with manage_tab:
        st.subheader("Manage an Open Trade")
        if not journal_open:
            st.info("There are no open trades to manage.")
        else:
            selected_trade_id = st.selectbox(
                "Trade",
                [trade.id for trade in journal_open],
                format_func=lambda value: next(f"{trade.symbol} · {trade.entry_price:.2f} · {trade.status.title()}" for trade in journal_open if trade.id == value),
                key="journal_manage_trade",
            )
            selected_trade = get_trade(selected_trade_id)
            if selected_trade:
                edit_tab, update_tab, exit_tab = st.tabs(["Edit Plan", "Management Update", "Record Exit"])
                with edit_tab:
                    edit_1, edit_2, edit_3, edit_4 = st.columns(4)
                    edit_stop = edit_1.number_input("Current Stop", min_value=0.0, value=float(selected_trade.current_stop or 0.0), step=0.01, key=f"edit_stop_{selected_trade.id}")
                    edit_t1 = edit_2.number_input("T1", min_value=0.0, value=float(selected_trade.t1 or 0.0), step=0.01, key=f"edit_t1_{selected_trade.id}")
                    edit_t2 = edit_3.number_input("T2", min_value=0.0, value=float(selected_trade.t2 or 0.0), step=0.01, key=f"edit_t2_{selected_trade.id}")
                    edit_t3 = edit_4.number_input("T3", min_value=0.0, value=float(selected_trade.t3 or 0.0), step=0.01, key=f"edit_t3_{selected_trade.id}")
                    edit_thesis = st.text_area("Current Thesis", value=selected_trade.thesis, key=f"edit_thesis_{selected_trade.id}")
                    edit_notes = st.text_area("Notes", value=selected_trade.notes, key=f"edit_notes_{selected_trade.id}")
                    if st.button("Save Trade Changes", width="stretch", key=f"save_edit_{selected_trade.id}"):
                        update_trade(selected_trade.id, current_stop=edit_stop or None, t1=edit_t1 or None, t2=edit_t2 or None, t3=edit_t3 or None, thesis=edit_thesis, notes=edit_notes)
                        st.success("Trade updated.")
                        st.rerun()

                with update_tab:
                    management_type = st.selectbox("Update Type", ["Management Note", "Stop Raised", "Target Reached", "Momentum Change", "Support Test", "AI Opinion Change", "News / Catalyst", "Risk Warning"], key=f"manage_type_{selected_trade.id}")
                    management_cols = st.columns(2)
                    management_price = management_cols[0].number_input("Current Price (optional)", min_value=0.0, value=0.0, step=0.01, key=f"manage_price_{selected_trade.id}")
                    management_stop = management_cols[1].number_input("New Stop (optional)", min_value=0.0, value=float(selected_trade.current_stop or 0.0), step=0.01, key=f"manage_stop_{selected_trade.id}")
                    management_note = st.text_area("What changed?", key=f"manage_note_{selected_trade.id}")
                    if st.button("Add Management Update", width="stretch", key=f"add_update_{selected_trade.id}"):
                        add_management_update(selected_trade.id, management_type, management_note, management_stop or None, management_price or None)
                        st.success("Management update added.")
                        st.rerun()

                with exit_tab:
                    exit_cols = st.columns(3)
                    exit_shares = exit_cols[0].number_input("Shares to Exit", min_value=0.0, max_value=float(selected_trade.remaining_shares), value=float(selected_trade.remaining_shares), step=1.0, key=f"exit_shares_{selected_trade.id}")
                    exit_price = exit_cols[1].number_input("Exit Price", min_value=0.0, value=0.0, step=0.01, key=f"exit_price_{selected_trade.id}")
                    exit_date = exit_cols[2].date_input("Exit Date", key=f"exit_date_{selected_trade.id}")
                    exit_reason = st.selectbox("Exit Reason", ["Target Hit", "Stop Hit", "Thesis Invalidated", "Momentum Faded", "Risk Reduction", "Earnings / Catalyst Risk", "Manual Exit", "Other"], key=f"exit_reason_{selected_trade.id}")
                    exit_notes = st.text_area("Exit Notes", key=f"exit_notes_{selected_trade.id}")
                    if st.button("Record Exit", type="primary", width="stretch", key=f"record_exit_{selected_trade.id}"):
                        try:
                            add_exit(selected_trade.id, exit_shares, exit_price, exit_reason, exit_notes, f"{exit_date.isoformat()}T00:00:00+00:00")
                            st.success("Exit recorded. The trade was closed if all remaining shares were exited.")
                            st.rerun()
                        except Exception as error:
                            st.error(str(error))

                st.divider()
                if st.button("Delete Trade Permanently", key=f"delete_trade_{selected_trade.id}"):
                    delete_trade(selected_trade.id)
                    st.success("Trade deleted.")
                    st.rerun()

    with closed_tab:
        st.subheader("Closed Trades & Post-Trade Review")
        if not journal_closed:
            render_empty_state("No closed trades yet", "Closed trades will appear here after the final exit is recorded.", "📒")
        else:
            closed_rows = [trade_summary(trade) for trade in journal_closed]
            st.dataframe(pd.DataFrame(closed_rows), width="stretch", hide_index=True)
            closed_id = st.selectbox(
                "Review Trade",
                [trade.id for trade in journal_closed],
                format_func=lambda value: next(f"{trade.symbol} · {trade.entry_price:.2f}" for trade in journal_closed if trade.id == value),
                key="journal_closed_trade",
            )
            closed_trade = get_trade(closed_id)
            if closed_trade:
                mode_label = classification_label(closed_trade.review_mode)
                st.markdown(f"### Trade Intelligence: {mode_label}")
                st.caption(closed_trade.classification_reason or "Classification is based on the evidence attached to this trade.")
                intel_cols = st.columns(3)
                intel_cols[0].metric("Review Mode", mode_label)
                intel_cols[1].metric("Intelligence Score", f"{closed_trade.intelligence_score:.0f}/100")
                intel_cols[2].metric("Evidence Categories", len(closed_trade.evidence))
                if closed_trade.evidence:
                    with st.expander("Broker & Plan Evidence", expanded=False):
                        st.dataframe(pd.DataFrame([{"Evidence": e.get("label"), "Source": e.get("source"), "Confidence": e.get("confidence"), "Observed": e.get("observed_at")} for e in closed_trade.evidence]), width="stretch", hide_index=True)
                if closed_trade.timeline:
                    with st.expander("Complete Trade Timeline", expanded=False):
                        st.dataframe(pd.DataFrame([{
                            "Time": e.get("time_label") or e.get("event_at") or "Time unavailable",
                            "Event": e.get("title"),
                            "Details": e.get("description"),
                            "Source": e.get("source"),
                            "Confidence": e.get("confidence"),
                        } for e in closed_trade.timeline]), width="stretch", hide_index=True)
                if closed_trade.review_mode == "historical_reconstruction":
                    st.markdown("#### Historical Reconstruction")
                    if st.button("Reconstruct Historical Entry", key=f"reconstruct_{closed_trade.id}"):
                        try:
                            reconstruction = reconstruct_trade(closed_trade, st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_SECRET_KEY"])
                            update_trade(closed_trade.id, reconstruction=reconstruction)
                            st.success("Historical entry reconstructed without hindsight contamination.")
                            st.rerun()
                        except Exception as error:
                            st.error(f"Reconstruction failed: {error}")
                    if closed_trade.reconstruction:
                        rc = closed_trade.reconstruction
                        rc_cols = st.columns(5)
                        rc_cols[0].metric("Objective Entry Grade", rc.get("objective_entry_grade", "—"))
                        rc_cols[1].metric("Entry Quality Score", rc.get("objective_entry_score", "—"))
                        rc_cols[2].metric("Likely Setup", rc.get("likely_setup", "—"))
                        rc_cols[3].metric("Setup Confidence", f"{rc.get('setup_confidence', 0):.0f}%")
                        reconstruction_confidence = rc.get("evidence_confidence")
                        if reconstruction_confidence in (None, "", 0, 0.0):
                            reconstruction_confidence = 96 if rc.get("intraday_execution_context") else 78 if (rc.get("daily_context") or rc.get("entry_context")) else 0
                        rc_cols[4].metric("Evidence Confidence", f"{float(reconstruction_confidence):.0f}%")
                        quality_label = rc.get("reconstruction_quality") or ("Excellent" if float(reconstruction_confidence) >= 90 else "Good" if float(reconstruction_confidence) >= 75 else "Limited")
                        st.caption(f"Reconstruction Quality: {quality_label}")

                        st.markdown("#### Chart Snapshot")
                        render_chart_thumbnail(rc.get("chart_snapshot"), f"{closed_trade.symbol} · pre-entry daily context")

                        st.markdown("#### AI Coach Summary")
                        render_coach_summary(build_reconstruction_coach(rc))

                        st.caption(
                            f"Broker entry: {str(rc.get('entry_execution_time') or '—').replace('T', ' ')} · "
                            f"Daily context: {str(rc.get('daily_context_as_of') or '—').replace('T', ' ')} · "
                            f"Intraday context: {str(rc.get('intraday_context_as_of') or 'Unavailable').replace('T', ' ')} "
                            f"({rc.get('intraday_timeframe', '—')})"
                        )

                        matched_stops = [
                            order for order in load_broker_orders()
                            if order.matched_trade_id == closed_trade.id and "Stop" in str(order.purpose or "")
                        ]
                        if matched_stops:
                            matched_stops = sorted(
                                matched_stops,
                                key=lambda order: order.submitted_at or order.created_at or order.cancelled_at or order.updated_at or "",
                            )
                            stop_prices = [float(order.stop_price or order.limit_price or 0) for order in matched_stops if (order.stop_price or order.limit_price)]
                            if stop_prices:
                                stop_cols = st.columns(3)
                                stop_cols[0].metric("Broker-Observed Initial Stop", f"${stop_prices[0]:.2f}")
                                stop_cols[1].metric("Broker-Observed Final Stop", f"${stop_prices[-1]:.2f}")
                                stop_cols[2].metric("Stop Evidence Confidence", f"{max(order.purpose_confidence for order in matched_stops):.0f}%")
                                st.caption("These stops come from Webull order evidence. They are separate from any saved MomoPro Official Plan stop.")

                        daily_context = rc.get("daily_context") or rc.get("entry_context") or {}
                        intraday_context = rc.get("intraday_execution_context") or {}
                        st.markdown("##### Daily Setup Context")
                        daily_cols = st.columns(6)
                        daily_cols[0].metric("Entry", f"${float(daily_context.get('entry_price') or closed_trade.entry_price):.2f}")
                        daily_cols[1].metric("EMA21", f"${float(daily_context.get('ema21') or 0):.2f}")
                        daily_cols[2].metric("EMA50", f"${float(daily_context.get('ema50') or 0):.2f}")
                        daily_cols[3].metric("EMA200", f"${float(daily_context.get('ema200') or 0):.2f}")
                        daily_cols[4].metric("RSI14", f"{float(daily_context.get('rsi14') or 0):.1f}")
                        daily_cols[5].metric("RVOL", f"{float(daily_context.get('rvol') or 0):.2f}")
                        st.caption(
                            f"Distance from EMA21: {float(daily_context.get('distance_from_ema21_pct') or 0):.2f}% · "
                            f"ATR%: {float(daily_context.get('atr_pct') or 0):.2f}%"
                        )

                        if intraday_context:
                            st.markdown("##### Intraday Execution Context")
                            intra_cols = st.columns(5)
                            intra_cols[0].metric("Entry", f"${float(intraday_context.get('entry_price') or closed_trade.entry_price):.2f}")
                            intra_cols[1].metric("EMA21", f"${float(intraday_context.get('ema21') or 0):.2f}")
                            intra_cols[2].metric("EMA50", f"${float(intraday_context.get('ema50') or 0):.2f}")
                            intra_cols[3].metric("RSI14", f"{float(intraday_context.get('rsi14') or 0):.1f}")
                            intra_cols[4].metric("RVOL", f"{float(intraday_context.get('rvol') or 0):.2f}")
                            st.caption(f"Distance from intraday EMA21: {float(intraday_context.get('distance_from_ema21_pct') or 0):.2f}%")

                        st.info(rc.get("hindsight_guard", "Historical reconstruction uses only information available before entry."))
                        st.caption(
                            f"Personal thesis: {rc.get('personal_thesis', 'Unknown — not recorded')} · "
                            f"Planned targets: {rc.get('planned_targets', 'Unknown — not recorded')} · "
                            f"Rule following: {rc.get('rule_following', 'Not gradable')}"
                        )
                review_1, review_2 = st.columns(2)
                followed = review_1.selectbox("Did you follow the planned exit?", ["Not Reviewed", "Yes", "Mostly", "No"], index=["Not Reviewed", "Yes", "Mostly", "No"].index(closed_trade.planned_exit_followed if closed_trade.planned_exit_followed in ["Not Reviewed", "Yes", "Mostly", "No"] else "Not Reviewed"), key=f"review_followed_{closed_trade.id}")
                rule_score = review_2.slider("Plan / Rule Following Score", 0, 100, int(closed_trade.rule_following_score or 0), key=f"review_score_{closed_trade.id}")
                strengths = st.text_area("What Went Right / Biggest Strength", value=closed_trade.strengths, key=f"review_strengths_{closed_trade.id}")
                mistakes = st.text_area("What Went Wrong / Biggest Mistake", value=closed_trade.mistakes, key=f"review_mistakes_{closed_trade.id}")
                lessons = st.text_area("Lessons Learned", value=closed_trade.lessons, key=f"review_lessons_{closed_trade.id}")
                ai_review = st.text_area("AI Coaching / Post-Trade Review", value=closed_trade.ai_review, help="This field stores the AI review when one is generated or pasted. Automated coaching is expanded in the Learning phase.", key=f"review_ai_{closed_trade.id}")
                if st.button("Save Post-Trade Review", type="primary", width="stretch", key=f"save_review_{closed_trade.id}"):
                    update_trade(closed_trade.id, planned_exit_followed=followed, rule_following_score=rule_score, strengths=strengths, mistakes=mistakes, lessons=lessons, ai_review=ai_review)
                    st.success("Post-trade review saved.")
                    st.rerun()
                if st.button("Reopen Trade", key=f"reopen_{closed_trade.id}"):
                    reopen_trade(closed_trade.id)
                    st.success("Trade reopened.")
                    st.rerun()


    with broker_tab:
        st.subheader("Webull Historical Import & Reconciliation")
        st.caption(
            "Upload Webull filled-order or execution history. MomoPro stores each execution once, "
            "matches buys and sells into journal trades, and keeps unmatched rows visible instead of guessing."
        )
        st.info(
            "Webull OpenAPI is the normal daily read-only sync. CSV import remains available for historical "
            "backfill, recovery, and reconciliation. MomoPro never places, modifies, or cancels orders."
        )

        st.markdown("#### Official Webull OpenAPI — Read Only")
        webull_api_key = _secret("WEBULL_APP_KEY")
        webull_api_secret = _secret("WEBULL_APP_SECRET")
        try:
            webull_section = st.secrets.get("webull", {})
            webull_api_key = webull_api_key or webull_section.get("app_key")
            webull_api_secret = webull_api_secret or webull_section.get("app_secret")
            webull_environment = str(webull_section.get("environment", "production"))
        except Exception:
            webull_environment = "production"

        api_status = webull_connection_status()
        status_label = str(api_status.get("status") or "not_connected").replace("_", " ").title()
        sync_status_value = str(api_status.get("sync_status") or "not_synced")
        sync_status_label = {
            "complete": "Complete",
            "partial_history": "History still importing",
            "not_synced": "Not synced yet",
        }.get(sync_status_value, sync_status_value.replace("_", " ").title())
        last_sync_text = str(api_status.get("last_sync") or "Not synced yet").replace("T", " ")
        if len(last_sync_text) > 19 and last_sync_text != "Not synced yet":
            last_sync_text = last_sync_text[:19] + " UTC"
        st.markdown(
            f"""
            <div class="momo-status-grid">
                <div class="momo-status-card"><div class="momo-status-label">Connection status</div><div class="momo-status-value">{status_label}</div></div>
                <div class="momo-status-card"><div class="momo-status-label">Sync status</div><div class="momo-status-value">{sync_status_label}</div></div>
                <div class="momo-status-card"><div class="momo-status-label">Access mode</div><div class="momo-status-value">Read only</div></div>
                <div class="momo-status-card"><div class="momo-status-label">Accounts discovered</div><div class="momo-status-value">{api_status.get("accounts", 0)}</div></div>
                <div class="momo-status-card"><div class="momo-status-label">Live positions</div><div class="momo-status-value">{api_status.get("positions", 0)}</div></div>
                <div class="momo-status-card"><div class="momo-status-label">Last synchronization</div><div class="momo-status-value">{last_sync_text}</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if api_status.get("message"):
            st.caption(f"Connection message: {api_status.get('message')}")
        pending_details = int(api_status.get("pending_detail_count") or 0)
        if sync_status_value == "partial_history":
            pending_text = (
                f"{pending_details} historical order detail request(s) remain pending and will retry safely on the next sync."
                if pending_details
                else "Some historical order details remain pending and will retry safely on the next sync."
            )
            st.info(pending_text)

        if not webull_api_key or not webull_api_secret:
            st.warning(
                "Webull credentials are missing. In Streamlit Secrets use either "
                "[webull] app_key/app_secret or WEBULL_APP_KEY/WEBULL_APP_SECRET."
            )
        sync_cols = st.columns([1, 1, 2])
        history_days = sync_cols[0].number_input("Order history days", 30, 3650, 730, step=30, key="webull_history_days")
        sync_clicked = sync_cols[1].button(
            "Sync Webull Now",
            type="primary",
            width="stretch",
            disabled=not bool(webull_api_key and webull_api_secret),
            key="sync_webull_openapi",
        )
        sync_cols[2].caption(
            "Pulls accounts, balances, current positions, open/filled orders and executions, then reconciles "
            "new fills into Journal and Performance with duplicate protection."
        )
        if sync_clicked:
            with st.spinner("Synchronizing Webull in read-only mode..."):
                sync_output = sync_webull(
                    str(webull_api_key),
                    str(webull_api_secret),
                    environment=webull_environment,
                    history_days=int(history_days),
                )
            sync_result = sync_output.get("result", {})
            if sync_result.get("ok"):
                st.success(
                    f"Webull sync complete: {sync_result.get('accounts', 0)} account(s), "
                    f"{sync_result.get('positions', 0)} position(s), {sync_result.get('orders', 0)} order(s), "
                    f"and {sync_result.get('new_executions', 0)} new execution(s)."
                )
                if sync_result.get("errors"):
                    st.warning(
                        "Sync completed, but a small part of historical order processing remains. "
                        "The app will continue safely on the next sync without duplicating completed imports."
                    )
                st.rerun()
            else:
                st.error("Webull sync failed: " + " | ".join(sync_result.get("errors") or ["Unknown error"]))

        webull_snapshot = load_webull_snapshot()
        balances = list((webull_snapshot.get("balances") or {}).values())
        if balances:
            st.markdown("##### Account Snapshot")
            st.dataframe(pd.DataFrame([{
                "Account": next((a.get("masked_account") for a in webull_snapshot.get("accounts", []) if a.get("account_id") == item.get("account_id")), "—"),
                "Net Liquidation": item.get("net_liquidation"),
                "Cash": item.get("cash_balance"),
                "Buying Power": item.get("buying_power"),
                "Market Value": item.get("market_value"),
                "Unrealized P/L": item.get("unrealized_pnl"),
                "Realized P/L": item.get("realized_pnl"),
            } for item in balances]), width="stretch", hide_index=True)

        live_positions = [item for item in webull_snapshot.get("positions", []) if item.get("symbol")]
        if live_positions:
            st.markdown("##### Current Webull Positions")
            st.dataframe(pd.DataFrame([{
                "Symbol": item.get("symbol"),
                "Quantity": item.get("quantity"),
                "Average Cost": item.get("average_cost"),
                "Last Price": item.get("last_price"),
                "Market Value": item.get("market_value"),
                "Unrealized P/L": item.get("unrealized_pnl"),
            } for item in live_positions]), width="stretch", hide_index=True)

        recent_orders = [
            item for item in (webull_snapshot.get("orders", []) or [])
            if item.get("order_id") and (item.get("symbol") or item.get("side") or item.get("quantity") or item.get("filled_quantity"))
        ][:100]
        if recent_orders:
            with st.expander(f"Recent Webull Orders ({len(webull_snapshot.get('orders', []))})"):
                st.dataframe(pd.DataFrame([{
                    "Submitted": item.get("submitted_at") or item.get("created_at") or "—",
                    "Updated / Event Time": item.get("updated_at") or "—",
                    "Symbol": item.get("symbol"),
                    "Side": item.get("side"),
                    "Status": item.get("status"),
                    "Quantity": item.get("quantity"),
                    "Filled": item.get("filled_quantity"),
                    "Average Price": item.get("average_price"),
                    "Stop Price": item.get("stop_price"),
                    "Order ID": item.get("order_id"),
                } for item in recent_orders]), width="stretch", hide_index=True)

        permanent_orders = load_broker_orders()
        canceled_orders = [o for o in permanent_orders if o.status.upper().replace(" ", "_") in {"CANCELED", "CANCELLED"}]
        if canceled_orders:
            with st.expander(f"Canceled-Order Intelligence ({len(canceled_orders)})"):
                st.caption("Canceled orders are preserved permanently and used as evidence. They never change shares or realized P/L.")
                st.dataframe(pd.DataFrame([{
                    "Submitted": (o.submitted_at or o.created_at) if has_reliable_broker_time(o) else "Unavailable from historical API",
                    "Canceled": (o.cancelled_at or o.updated_at) if has_reliable_broker_time(o) else "Unavailable from historical API",
                    "Observed by Sync": o.synced_at or "—",
                    "Symbol": o.symbol,
                    "Side": o.side,
                    "Type": o.order_type,
                    "Quantity": o.quantity,
                    "Stop": o.stop_price or None,
                    "Limit": o.limit_price or None,
                    "Classification": o.purpose,
                    "Confidence": o.purpose_confidence,
                    "Trade ID": o.matched_trade_id or "—",
                } for o in sorted(canceled_orders, key=lambda x: x.cancelled_at or x.updated_at or x.submitted_at or "", reverse=True)[:250]]), width="stretch", hide_index=True)

        sync_summary = webull_snapshot.get("sync_summary") or {}
        sync_warnings = sync_summary.get("errors") or []
        if sync_warnings:
            rate_limit_related = [
                item for item in sync_warnings
                if "deferred" in str(item).lower() or "rate limit" in str(item).lower() or "429" in str(item)
            ]
            other_warnings = [item for item in sync_warnings if item not in rate_limit_related]
            if rate_limit_related:
                st.warning(
                    "Historical Webull orders are being imported in safe, rate-limited batches. "
                    "Run Sync Webull Now again after this sync finishes to continue any deferred history. "
                    "Already imported executions will not be duplicated."
                )
            if other_warnings:
                with st.expander(f"Webull sync details ({len(other_warnings)})"):
                    for item in other_warnings:
                        st.write(f"• {item}")

        diagnostics = webull_snapshot.get("diagnostics") or {}
        if diagnostics:
            with st.expander("Safe Webull response diagnostics"):
                st.caption(
                    "This shows response field names and container sizes only. It does not display your API key, "
                    "API secret, account balances, order values, or other credential values."
                )
                st.json(diagnostics)

        st.divider()
        st.markdown("#### Webull CSV Backfill & Reconciliation")
        import_status = broker_import_status()
        broker_metrics = st.columns(5)
        broker_metrics[0].metric("Executions", import_status.get("executions", 0))
        broker_metrics[1].metric("CSV Imports", import_status.get("imports", 0))
        broker_metrics[2].metric("Unmatched", import_status.get("unmatched", 0))
        broker_metrics[3].metric("Duplicates Skipped", import_status.get("duplicates_skipped", 0))
        broker_metrics[4].metric("Last Import", str(import_status.get("last_import") or "—")[:10])

        webull_file = st.file_uploader(
            "Upload Webull CSV",
            type=["csv", "txt"],
            key="webull_history_csv",
            help="Use a Webull order/execution-history export containing filled trades.",
        )

        if webull_file is not None:
            csv_bytes = webull_file.getvalue()
            preview = preview_webull_csv(csv_bytes, webull_file.name)
            if not preview.get("ok"):
                st.error(preview.get("error") or "This CSV could not be read.")
                if preview.get("columns"):
                    st.caption("Columns found: " + ", ".join(preview["columns"]))
            else:
                st.success(
                    f"Detected {len(preview.get('rows', []))} filled executions from "
                    f"{preview.get('rows_seen', 0)} CSV rows."
                )
                mapping_rows = [
                    {"Required Field": key, "Detected Column": value or "Not found"}
                    for key, value in preview.get("mapping", {}).items()
                ]
                with st.expander("Detected column mapping"):
                    st.dataframe(pd.DataFrame(mapping_rows), width="stretch", hide_index=True)
                preview_rows = preview.get("rows", [])[:25]
                if preview_rows:
                    st.dataframe(
                        pd.DataFrame([
                            {
                                "Time": row.get("executed_at"),
                                "Symbol": row.get("symbol"),
                                "Side": row.get("side"),
                                "Quantity": row.get("quantity"),
                                "Price": row.get("price"),
                                "Fees": row.get("fees"),
                                "Order ID": row.get("order_id") or "—",
                            }
                            for row in preview_rows
                        ]),
                        width="stretch",
                        hide_index=True,
                    )
                if preview.get("skipped"):
                    with st.expander(f"Skipped rows ({len(preview['skipped'])})"):
                        for message in preview["skipped"][:100]:
                            st.caption(message)
                st.warning(
                    "Review the preview before importing. Importing the same file again is safe because "
                    "each execution has a stable duplicate fingerprint."
                )
                if st.button("Import and Reconcile Webull History", type="primary", width="stretch", key="import_webull_csv"):
                    try:
                        result = import_webull_history(csv_bytes, webull_file.name)
                        imported = result.get("import", {})
                        reconciled = result.get("reconciliation", {})
                        st.success(
                            f"Imported {imported.get('rows_imported', 0)} new executions; "
                            f"skipped {imported.get('duplicates_skipped', 0)} duplicates."
                        )
                        st.write(
                            f"Created {reconciled.get('new_trades', 0)} trades, "
                            f"updated {reconciled.get('updated_trades', 0)}, "
                            f"closed {reconciled.get('closed_trades', 0)}, and left "
                            f"{len(result.get('unmatched', []))} executions unmatched."
                        )
                        st.rerun()
                    except Exception as error:
                        st.error(str(error))

        imports = load_broker_imports()
        if imports:
            st.markdown("#### Import History")
            st.dataframe(
                pd.DataFrame([
                    {
                        "Imported At": item.imported_at,
                        "File": item.source_file,
                        "Rows Seen": item.rows_seen,
                        "Imported": item.rows_imported,
                        "Duplicates": item.duplicates_skipped,
                        "Skipped": item.rows_skipped,
                    }
                    for item in imports[:20]
                ]),
                width="stretch",
                hide_index=True,
            )

        broker_executions = load_broker_executions()
        unmatched = [item for item in broker_executions if not item.matched_trade_id]
        if unmatched:
            st.markdown("#### Unmatched Broker Executions")
            st.warning(
                "These executions were preserved but not forced into a journal trade. This commonly happens "
                "when the CSV begins with a sell from a position opened before the export range."
            )
            st.dataframe(
                pd.DataFrame([
                    {
                        "Time": item.executed_at,
                        "Symbol": item.symbol,
                        "Side": item.side,
                        "Quantity": item.quantity,
                        "Price": item.price,
                        "Order ID": item.order_id or "—",
                        "File": item.source_file,
                    }
                    for item in unmatched
                ]),
                width="stretch",
                hide_index=True,
            )


# -----------------------------
# Performance Analytics
# -----------------------------
if active_page_is("Performance"):
    st.header("Performance Analytics")
    st.caption(
        "Analyze completed journal trades and historical Webull executions from one reconciled performance record."
    )

    performance_trades = load_trades()
    performance_executions = load_broker_executions()
    performance_imports = load_broker_imports()
    performance_frame_all = trades_to_frame(performance_trades)

    if performance_frame_all.empty:
        st.info(
            "No completed trades are available yet. Import Webull history in Journal → Broker Import & Reconcile, "
            "or close a journal trade to unlock analytics."
        )
        quality = data_quality_report(performance_frame_all, performance_executions, performance_imports)
        empty_cols = st.columns(4)
        empty_cols[0].metric("Broker Executions", quality["broker_executions"])
        empty_cols[1].metric("Matched Executions", quality["matched_executions"])
        empty_cols[2].metric("Unmatched", quality["unmatched_executions"])
        empty_cols[3].metric("Import Files", quality["imports"])
    else:
        st.markdown("### Performance Filters")
        filter_cols = st.columns([1.3, 1.7, 1, 1])
        with filter_cols[0]:
            default_perf_source = get_setting(
                "performance.default_source_filter", "All Trades", st.session_state.momopro_settings
            )
            performance_source = st.selectbox(
                "Trade source",
                SOURCE_OPTIONS,
                index=SOURCE_OPTIONS.index(default_perf_source) if default_perf_source in SOURCE_OPTIONS else 0,
                key="performance_source_filter",
            )
        available_symbols = sorted(performance_frame_all["symbol"].dropna().unique().tolist())
        with filter_cols[1]:
            performance_symbols = st.multiselect(
                "Symbols",
                available_symbols,
                default=[],
                placeholder="All symbols",
                key="performance_symbol_filter",
            )
        exit_dates = performance_frame_all["exit_date"].dropna()
        min_exit_date = exit_dates.min().date() if not exit_dates.empty else None
        max_exit_date = exit_dates.max().date() if not exit_dates.empty else None
        with filter_cols[2]:
            performance_start = st.date_input(
                "From",
                value=min_exit_date,
                min_value=min_exit_date,
                max_value=max_exit_date,
                key="performance_start_date",
            ) if min_exit_date else None
        with filter_cols[3]:
            performance_end = st.date_input(
                "Through",
                value=max_exit_date,
                min_value=min_exit_date,
                max_value=max_exit_date,
                key="performance_end_date",
            ) if max_exit_date else None

        performance_frame = filter_performance_frame(
            performance_frame_all,
            source=performance_source,
            symbols=performance_symbols,
            start_date=performance_start,
            end_date=performance_end,
        )
        summary = calculate_summary(performance_frame)
        review = review_metrics(performance_frame)
        quality = data_quality_report(performance_frame, performance_executions, performance_imports)
        insights = build_performance_insights(performance_frame, summary, review)

        if performance_frame.empty:
            st.warning("No completed trades match the selected filters.")
        else:
            st.markdown("### Performance Snapshot")
            metric_row_1 = st.columns(6)
            metric_row_1[0].metric("Net P/L", money_text(summary["net_pnl"]))
            metric_row_1[1].metric("Win Rate", percent_text(summary["win_rate"]))
            metric_row_1[2].metric("Completed Trades", summary["trades"])
            metric_row_1[3].metric(
                "Profit Factor",
                f"{summary['profit_factor']:.2f}" if summary["profit_factor"] is not None else "—",
            )
            metric_row_1[4].metric("Expectancy", money_text(summary["expectancy"]))
            metric_row_1[5].metric("Average R", r_text(summary["average_r"]))

            metric_row_2 = st.columns(6)
            metric_row_2[0].metric("Average Winner", money_text(summary["avg_winner"]))
            metric_row_2[1].metric("Average Loser", money_text(summary["avg_loser"]))
            metric_row_2[2].metric("Average Hold", f"{summary['average_hold_days']:.1f} days" if summary["average_hold_days"] is not None else "—")
            metric_row_2[3].metric("Longest Win Streak", summary["longest_win_streak"])
            metric_row_2[4].metric("Longest Loss Streak", summary["longest_loss_streak"])
            metric_row_2[5].metric("Broker Fees", money_text(summary["fees"]))

            best_worst = st.columns(2)
            best_trade = summary.get("best_trade") or {}
            worst_trade = summary.get("worst_trade") or {}
            with best_worst[0]:
                st.success(
                    f"Best trade: {best_trade.get('symbol', '—')} · {money_text(best_trade.get('net_pnl'))}"
                )
            with best_worst[1]:
                st.error(
                    f"Worst trade: {worst_trade.get('symbol', '—')} · {money_text(worst_trade.get('net_pnl'))}"
                )

            st.markdown("### Performance Intelligence")
            st.info(insights["headline"])
            insight_cols = st.columns(3)
            with insight_cols[0]:
                st.markdown("**What is working**")
                if insights.get("strengths"):
                    for item in insights["strengths"]:
                        st.write(f"• {item}")
                else:
                    st.caption("More labeled trades are needed to identify dependable strengths.")
            with insight_cols[1]:
                st.markdown("**Risks and weak spots**")
                if insights.get("risks"):
                    for item in insights["risks"]:
                        st.write(f"• {item}")
                else:
                    st.caption("No major weakness is confirmed by the current sample.")
            with insight_cols[2]:
                st.markdown("**Next improvements**")
                for item in insights.get("next_actions", []):
                    st.write(f"• {item}")

            chart_cols = st.columns(2)
            with chart_cols[0]:
                st.markdown("### Equity Curve")
                curve = equity_curve(performance_frame)
                if curve.empty:
                    st.caption("Exit dates are required to draw the equity curve.")
                else:
                    st.line_chart(curve.set_index("Date")[["Cumulative P/L"]], width="stretch")
            with chart_cols[1]:
                st.markdown("### Monthly Net P/L")
                monthly = monthly_performance(performance_frame)
                if monthly.empty:
                    st.caption("Monthly results will appear when dated exits are available.")
                else:
                    st.bar_chart(monthly.set_index("Month")[["Net P/L"]], width="stretch")

            perf_tabs = st.tabs([
                "Monthly",
                "Strategy",
                "Scores & AI",
                "Market Conditions",
                "Execution & Discipline",
                "Trade History",
                "Data Quality",
            ])

            with perf_tabs[0]:
                monthly = monthly_performance(performance_frame)
                if monthly.empty:
                    st.info("No dated monthly performance is available.")
                else:
                    st.dataframe(monthly, width="stretch", hide_index=True)

            with perf_tabs[1]:
                strategy_cols = st.columns(3)
                with strategy_cols[0]:
                    st.markdown("#### By Setup")
                    setup_table = group_performance(performance_frame, "setup", "Setup")
                    st.dataframe(setup_table, width="stretch", hide_index=True) if not setup_table.empty else st.caption("No setup labels yet.")
                with strategy_cols[1]:
                    st.markdown("#### By Grade")
                    grade_table = group_performance(performance_frame, "grade", "Grade")
                    st.dataframe(grade_table, width="stretch", hide_index=True) if not grade_table.empty else st.caption("No grades yet.")
                with strategy_cols[2]:
                    st.markdown("#### By Hold Time")
                    hold_table = group_performance(performance_frame, "hold_bucket", "Hold Time")
                    st.dataframe(hold_table, width="stretch", hide_index=True)

                secondary_strategy = st.columns(2)
                with secondary_strategy[0]:
                    st.markdown("#### By Price Range")
                    st.dataframe(group_performance(performance_frame, "price_range", "Price Range"), width="stretch", hide_index=True)
                with secondary_strategy[1]:
                    st.markdown("#### By Trade Source")
                    st.dataframe(group_performance(performance_frame, "source", "Source"), width="stretch", hide_index=True)

            with perf_tabs[2]:
                score_cols = st.columns(3)
                with score_cols[0]:
                    st.markdown("#### Momo Score")
                    st.dataframe(group_performance(performance_frame, "momo_score_band", "Momo Score"), width="stretch", hide_index=True)
                with score_cols[1]:
                    st.markdown("#### Opportunity Score")
                    st.dataframe(group_performance(performance_frame, "opportunity_band", "Opportunity Score"), width="stretch", hide_index=True)
                with score_cols[2]:
                    st.markdown("#### Independent AI Confidence")
                    st.dataframe(group_performance(performance_frame, "ai_confidence_band", "AI Confidence"), width="stretch", hide_index=True)

                ai_accuracy = decision_accuracy(
                    performance_frame,
                    "ai_action",
                    {"buy", "bullish", "accumulate", "watch closely", "long"},
                )
                accuracy_cols = st.columns(3)
                accuracy_cols[0].metric("AI Decision Coverage", percent_text(ai_accuracy["coverage"]))
                accuracy_cols[1].metric("AI Direction Accuracy", percent_text(ai_accuracy["accuracy"]))
                accuracy_cols[2].metric("AI-Labeled Sample", ai_accuracy["sample"])
                st.caption(
                    "Accuracy compares the saved Independent AI action at entry with the final profitable/loss outcome. "
                    "It is descriptive and becomes more reliable as labeled sample size grows."
                )

            with perf_tabs[3]:
                condition_cols = st.columns(2)
                with condition_cols[0]:
                    st.markdown("#### Market Regime")
                    st.dataframe(group_performance(performance_frame, "market_regime", "Market Regime"), width="stretch", hide_index=True)
                with condition_cols[1]:
                    st.markdown("#### Sector")
                    st.dataframe(group_performance(performance_frame, "sector", "Sector"), width="stretch", hide_index=True)

            with perf_tabs[4]:
                discipline_cols = st.columns(6)
                discipline_cols[0].metric("Reviewed Trades", review.get("reviewed_trades", 0))
                discipline_cols[1].metric("Plan Follow Rate", percent_text(review.get("planned_exit_follow_rate")))
                discipline_cols[2].metric("Rule Score", f"{review.get('average_rule_score'):.1f}/100" if review.get("average_rule_score") is not None else "—")
                discipline_cols[3].metric("Mistake Rate", percent_text(review.get("mistake_rate")))
                discipline_cols[4].metric("T1 Hit Rate", percent_text(review.get("target_hit_rate")))
                discipline_cols[5].metric("Stop Hit Rate", percent_text(review.get("stop_hit_rate")))

                planned_table = group_performance(performance_frame, "planned_exit_followed", "Planned Exit Followed")
                st.markdown("#### Planned vs. Actual Exit")
                st.dataframe(planned_table, width="stretch", hide_index=True)

                mistake_rows = performance_frame[performance_frame["mistakes"].astype(str).str.strip() != ""]
                if not mistake_rows.empty:
                    st.markdown("#### Documented Mistakes")
                    st.dataframe(
                        mistake_rows[["exit_date", "symbol", "net_pnl", "mistakes", "lessons"]].rename(columns={
                            "exit_date": "Exit Date", "symbol": "Symbol", "net_pnl": "Net P/L",
                            "mistakes": "Mistakes", "lessons": "Lessons",
                        }),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.caption("No post-trade mistakes have been documented yet.")

            with perf_tabs[5]:
                history_display = performance_frame[[
                    "exit_date", "symbol", "source", "entry_price", "average_exit_price", "shares",
                    "net_pnl", "realized_r", "outcome", "days_held", "setup", "grade",
                ]].copy()
                history_display = history_display.rename(columns={
                    "exit_date": "Exit Date", "symbol": "Symbol", "source": "Source",
                    "entry_price": "Entry", "average_exit_price": "Average Exit", "shares": "Shares",
                    "net_pnl": "Net P/L", "realized_r": "R", "outcome": "Outcome",
                    "days_held": "Days Held", "setup": "Setup", "grade": "Grade",
                })
                st.dataframe(history_display.sort_values("Exit Date", ascending=False), width="stretch", hide_index=True)

                selected_history_id = st.selectbox(
                    "Review trade timeline",
                    performance_frame["trade_id"].tolist(),
                    format_func=lambda trade_id: next(
                        (
                            f"{row['symbol']} · {row['exit_date'].date() if pd.notna(row['exit_date']) else 'Undated'} · {money_text(row['net_pnl'])}"
                            for _, row in performance_frame.iterrows() if row["trade_id"] == trade_id
                        ),
                        trade_id,
                    ),
                    key="performance_timeline_trade",
                )
                selected_trade = next((trade for trade in performance_trades if trade.id == selected_history_id), None)
                if selected_trade:
                    timeline = trade_timeline(selected_trade)
                    st.dataframe(timeline, width="stretch", hide_index=True)
                    review_cols = st.columns(2)
                    with review_cols[0]:
                        st.markdown("**Original thesis**")
                        st.write(selected_trade.thesis or "Not recorded.")
                        st.markdown("**What went right**")
                        st.write(selected_trade.strengths or "Not reviewed.")
                    with review_cols[1]:
                        st.markdown("**What went wrong**")
                        st.write(selected_trade.mistakes or "Not reviewed.")
                        st.markdown("**Lesson**")
                        st.write(selected_trade.lessons or "Not reviewed.")

            with perf_tabs[6]:
                st.markdown("#### Webull Reconciliation")
                quality_cols = st.columns(6)
                quality_cols[0].metric("Closed Records", quality["closed_trade_records"])
                quality_cols[1].metric("Broker Executions", quality["broker_executions"])
                quality_cols[2].metric("Matched", quality["matched_executions"])
                quality_cols[3].metric("Unmatched", quality["unmatched_executions"])
                quality_cols[4].metric("Reconciliation", percent_text(quality["reconciliation_rate"]))
                quality_cols[5].metric("Import Files", quality["imports"])

                coverage_frame = pd.DataFrame([
                    {"Metric": "Trades with R-multiple", "Coverage": quality["trades_with_r"], "Total": len(performance_frame)},
                    {"Metric": "Trades with AI Confidence", "Coverage": quality["trades_with_ai"], "Total": len(performance_frame)},
                    {"Metric": "Trades with setup labels", "Coverage": quality["trades_with_setup"], "Total": len(performance_frame)},
                    {"Metric": "Trades with post-trade review", "Coverage": quality["trades_reviewed"], "Total": len(performance_frame)},
                ])
                coverage_frame["Coverage %"] = (
                    coverage_frame["Coverage"] / coverage_frame["Total"].replace(0, pd.NA) * 100
                ).round(2)
                st.dataframe(coverage_frame, width="stretch", hide_index=True)

                st.markdown("#### Measurement Availability")
                st.write("• Scanner-to-trade conversion requires persistent historical scan snapshots, scheduled for the Learning/Data phases.")
                st.write("• Momo Engine directional accuracy requires saving the engine decision with each trade at entry; future trades will provide this coverage.")
                st.write("• Imported Webull history can calculate broker results immediately, but setup, AI, thesis, and rule analytics only exist where those fields were recorded.")



# -----------------------------
# Learning Engine
# -----------------------------
if active_page_is("Learning"):
    st.header("Learning Engine")
    st.caption(
        "Personalized edge detection, confidence calibration, mistake learning, and coaching from the same reconciled Journal and Webull history used by Performance Analytics."
    )

    learning_trades = load_trades()
    learning_frame_all = trades_to_frame(learning_trades)

    if learning_frame_all.empty:
        st.info(
            "No completed trades are available yet. Import Webull history or close Journal trades, then return here. "
            "MomoPro will not manufacture conclusions without recorded outcomes."
        )
    else:
        control_a, control_b, control_c = st.columns([1.4, 1.4, 1])
        learning_source = control_a.selectbox(
            "Learning source",
            SOURCE_OPTIONS,
            index=0,
            key="learning_source_filter",
        )
        learning_symbols = control_b.multiselect(
            "Symbols",
            sorted(learning_frame_all["symbol"].dropna().unique().tolist()),
            key="learning_symbol_filter",
        )
        minimum_samples = control_c.number_input(
            "Minimum samples / group",
            min_value=1,
            max_value=100,
            value=2,
            step=1,
            help="Small groups are still labeled honestly as insufficient data or early signals.",
            key="learning_min_samples",
        )

        learning_frame = filter_performance_frame(
            learning_frame_all,
            source=learning_source,
            symbols=learning_symbols,
        )
        report = build_learning_report(learning_frame, int(minimum_samples))
        coaching = build_coaching(report)

        sample = int(report["sample_size"])
        evidence = report["evidence"]
        weekly = report["weekly"]
        monthly = report["monthly"]
        metric_cols = st.columns(6)
        metric_cols[0].metric("Completed Trades", sample)
        metric_cols[1].metric("Evidence", evidence)
        metric_cols[2].metric("Weekly P/L", money_text(weekly["net_pnl"]))
        metric_cols[3].metric("Weekly Trades", weekly["trades"])
        metric_cols[4].metric("Monthly P/L", money_text(monthly["net_pnl"]))
        metric_cols[5].metric("Monthly Trades", monthly["trades"])

        if evidence == "Insufficient data":
            st.warning(coaching["disclaimer"])
        elif evidence == "Early signal":
            st.info(coaching["disclaimer"])
        else:
            st.success(coaching["disclaimer"])

        learning_tabs = st.tabs([
            "Edge Map", "Weaknesses & Mistakes", "Confidence Calibration",
            "Weekly / Monthly Coach", "Pattern Learning", "Strategy Rules", "Learning History",
        ])

        with learning_tabs[0]:
            st.markdown("#### Strongest Personalized Edges")
            edges = report["edges"]
            if edges.empty:
                st.info("No grouped edge has enough recorded samples yet.")
            else:
                st.dataframe(
                    edges[["Dimension", "Group", "Trades", "Win Rate %", "Net P/L", "Expectancy", "Average R", "Average Hold Days", "Evidence"]],
                    width="stretch",
                    hide_index=True,
                )
            st.markdown("#### Coaching: What Is Working")
            if coaching["strengths"]:
                for item in coaching["strengths"]:
                    st.write(f"• {item}")
            else:
                st.caption("No reliable strength has emerged yet. Keep recording complete trade context.")

            st.markdown("#### Detailed Edge Tables")
            for name, table in report["tables"].items():
                with st.expander(name, expanded=name in {"Setups", "Market Regimes"}):
                    if table.empty:
                        st.caption("Not enough labeled trades for this dimension.")
                    else:
                        st.dataframe(table, width="stretch", hide_index=True)

        with learning_tabs[1]:
            st.markdown("#### Weak Areas")
            weaknesses = report["weaknesses"]
            if weaknesses.empty:
                st.info("No repeated weak area has enough evidence yet.")
            else:
                st.dataframe(
                    weaknesses[["Dimension", "Group", "Trades", "Win Rate %", "Net P/L", "Expectancy", "Average R", "Evidence"]],
                    width="stretch",
                    hide_index=True,
                )

            st.markdown("#### Recorded Mistakes")
            mistakes = report["mistakes"]
            if mistakes.empty:
                st.caption("No structured mistakes have been recorded in post-trade reviews yet.")
            else:
                st.dataframe(mistakes, width="stretch", hide_index=True)

            st.markdown("#### Behavioral Signals")
            signals = report["behavior"].get("signals", [])
            if not signals:
                st.caption("No repeated behavioral signal has enough recorded context yet.")
            else:
                for signal in signals:
                    if signal.get("type") == "Strength":
                        st.success(f"{signal.get('name')}: {signal.get('detail')}")
                    elif signal.get("type") == "Risk":
                        st.warning(f"{signal.get('name')}: {signal.get('detail')}")
                    else:
                        st.info(f"{signal.get('name')}: {signal.get('detail')}")

        with learning_tabs[2]:
            st.markdown("#### Independent AI Confidence Calibration")
            ai_calibration = report["ai_calibration"]
            st.dataframe(ai_calibration, width="stretch", hide_index=True) if not ai_calibration.empty else st.caption("AI Confidence was not saved on enough completed trades.")
            st.markdown("#### Momo Score Calibration")
            momo_calibration = report["momo_calibration"]
            st.dataframe(momo_calibration, width="stretch", hide_index=True) if not momo_calibration.empty else st.caption("Momo Score coverage is not sufficient.")
            st.markdown("#### Opportunity Score Calibration")
            opportunity_calibration = report["opportunity_calibration"]
            st.dataframe(opportunity_calibration, width="stretch", hide_index=True) if not opportunity_calibration.empty else st.caption("Opportunity Score coverage is not sufficient.")
            st.caption(
                "Calibration compares recorded score bands with actual outcomes. It does not change scanner or AI thresholds automatically. "
                "Any strategy rule must be reviewed and approved below."
            )

        with learning_tabs[3]:
            review_cols = st.columns(2)
            with review_cols[0]:
                st.markdown("#### Weekly Review")
                st.metric("Trades", weekly["trades"])
                st.metric("Net P/L", money_text(weekly["net_pnl"]))
                st.metric("Win Rate", percent_text(weekly["win_rate"]))
                st.metric("Average R", r_text(weekly["average_r"]))
                st.caption(f"Evidence: {weekly['evidence']}")
            with review_cols[1]:
                st.markdown("#### Monthly Review")
                st.metric("Trades", monthly["trades"])
                st.metric("Net P/L", money_text(monthly["net_pnl"]))
                st.metric("Win Rate", percent_text(monthly["win_rate"]))
                st.metric("Average R", r_text(monthly["average_r"]))
                st.caption(f"Evidence: {monthly['evidence']}")

            st.markdown("#### Next Improvement Priority")
            for item in coaching["priorities"]:
                st.info(item)
            st.markdown("#### Current Risks")
            if coaching["risks"]:
                for item in coaching["risks"]:
                    st.write(f"• {item}")
            else:
                st.caption("No repeated risk has enough evidence yet.")

            if st.button("Save Current Learning Snapshot", width="stretch", key="save_learning_snapshot"):
                top_edge = None if report["edges"].empty else report["edges"].iloc[0].to_dict()
                top_weakness = None if report["weaknesses"].empty else report["weaknesses"].iloc[0].to_dict()
                save_learning_snapshot({
                    "source": learning_source,
                    "symbols": learning_symbols,
                    "sample_size": sample,
                    "evidence": evidence,
                    "weekly": weekly,
                    "monthly": monthly,
                    "top_edge": top_edge,
                    "top_weakness": top_weakness,
                    "priorities": coaching["priorities"],
                })
                st.success("Learning snapshot saved.")

        with learning_tabs[4]:
            st.markdown("#### Expanded Pattern Library")
            st.write(
                "The Trading Intelligence pattern engine now recognizes EMA21 reclaims/retests, higher-low continuations, bull flags, "
                "pennants, ascending/descending/symmetrical triangles, rising/falling wedges, volatility contractions, breakouts, cups and cup-and-handle candidates."
            )
            st.markdown("#### Personalized Pattern Outcomes")
            setup_table = report["tables"].get("Setups")
            if setup_table is None or setup_table.empty:
                st.info("Historical Webull trades may not have setup labels. Future MomoPro-planned trades will build pattern probabilities automatically.")
            else:
                st.dataframe(setup_table, width="stretch", hide_index=True)
            st.caption(
                "Pattern probabilities come only from completed trades whose setup was recorded. The engine labels sample strength and never treats a small sample as a proven edge."
            )

        with learning_tabs[5]:
            st.markdown("#### Human-Approved Strategy Rules")
            st.warning(
                "The Learning Engine does not silently rewrite your scanner, risk, or AI settings. It proposes evidence; you decide which rules become part of your process."
            )
            with st.form("new_learning_rule_form"):
                proposed_rule = st.text_input("Rule", placeholder="Example: Avoid entries more than 6% above EMA21")
                proposed_rationale = st.text_area("Evidence / rationale")
                if st.form_submit_button("Add Approved Rule", width="stretch"):
                    try:
                        add_approved_rule(proposed_rule, proposed_rationale)
                        st.success("Strategy rule saved.")
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))

            learning_data = load_learning_data()
            rules = learning_data.get("approved_rules", [])
            if not rules:
                st.caption("No personalized rules have been approved yet.")
            for rule in rules:
                cols = st.columns([0.8, 5, 1])
                enabled = cols[0].checkbox("On", value=bool(rule.get("enabled", True)), key=f"learning_rule_enabled_{rule.get('id')}")
                if enabled != bool(rule.get("enabled", True)):
                    set_learning_rule_enabled(rule.get("id"), enabled)
                    st.rerun()
                cols[1].markdown(f"**{rule.get('rule')}**  \n{rule.get('rationale') or 'No rationale recorded.'}")
                if cols[2].button("Delete", key=f"delete_learning_rule_{rule.get('id')}"):
                    delete_learning_rule(rule.get("id"))
                    st.rerun()

        with learning_tabs[6]:
            learning_data = load_learning_data()
            snapshots = list(reversed(learning_data.get("snapshots", [])))
            if not snapshots:
                st.info("Save a weekly or monthly learning snapshot to build a history of how your edge changes over time.")
            else:
                rows = []
                for snapshot in snapshots:
                    rows.append({
                        "Saved": snapshot.get("created_at"),
                        "Source": snapshot.get("source"),
                        "Trades": snapshot.get("sample_size"),
                        "Evidence": snapshot.get("evidence"),
                        "Weekly P/L": (snapshot.get("weekly") or {}).get("net_pnl"),
                        "Monthly P/L": (snapshot.get("monthly") or {}).get("net_pnl"),
                        "Top Edge": (snapshot.get("top_edge") or {}).get("Group"),
                        "Top Weakness": (snapshot.get("top_weakness") or {}).get("Group"),
                    })
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# -----------------------------
# Settings & Personalization
# -----------------------------
if active_page_is("Settings"):
    st.header("Settings & Personalization")
    st.caption(
        "One persistent profile for strategy, risk, scanner, AI, dashboard, journal, performance, alerts, and integrations."
    )

    settings = get_settings()
    st.session_state.momopro_settings = settings
    summary = settings_summary(settings)
    displayed_account_size, account_size_source = get_effective_account_size(settings)
    broker_context = get_account_context(settings, refresh=False)
    summary_cols = st.columns(5)
    summary_cols[0].metric("Trading Style", summary["Trading style"])
    summary_cols[1].metric("Account Size", money_text(displayed_account_size), help=f"Source: {account_size_source}")
    summary_cols[1].caption(f"Source: {account_size_source}")
    summary_cols[2].metric("Risk / Trade", percent_text(summary["Risk / trade"]))
    summary_cols[3].metric("AI Style", summary["AI style"])
    summary_cols[4].metric("Default Universe", summary["Dashboard universe"])

    st.info(
        "Settings are saved to your private Supabase workspace, with `settings_data.json` retained only as a local backup/export layer. "
        "Account size is resolved once through the canonical Webull account context and reused by Settings, Trade Planner, risk calculations, and future journal automation. The editable Risk value is only a fallback."
    )
    if account_size_source != "Manual fallback":
        st.caption(
            f"Webull context: cash {money_text(broker_context.cash_balance)} · "
            f"positions {money_text(broker_context.market_value)} · "
            f"buying power {money_text(broker_context.buying_power)} · "
            f"last sync {broker_context.last_sync or '—'}"
        )

    settings_tabs = st.tabs([
        "Profile", "Risk", "Scanner", "Indicators", "AI Behavior",
        "Dashboard", "Journal & Performance", "Alerts", "Data & Integrations", "Backup & Reset",
    ])

    with settings_tabs[0]:
        profile = settings["profile"]
        with st.form("settings_profile_form"):
            display_name = st.text_input("Display name", value=profile.get("display_name", "Dee"))
            trading_style = st.selectbox(
                "Trading style", ["Day Trading", "Swing Trading", "Position Trading", "Mixed"],
                index=["Day Trading", "Swing Trading", "Position Trading", "Mixed"].index(profile.get("trading_style", "Swing Trading")),
            )
            typical_hold_days = st.number_input("Typical hold period (days)", 1, 365, int(profile.get("typical_hold_days", 10)))
            setup_options = ["EMA21 Reclaim", "EMA21 Retest", "Higher-Low Continuation", "Bull Flag", "Ascending Triangle", "Breakout", "Pullback"]
            preferred_setups = st.multiselect("Preferred setups", setup_options, default=[x for x in profile.get("preferred_setups", []) if x in setup_options])
            preferred_sectors = st.multiselect(
                "Preferred sectors", ["Technology", "Semiconductors", "Healthcare", "Biotechnology", "Financials", "Energy", "Industrials", "Consumer", "Communication Services"],
                default=profile.get("preferred_sectors", []),
            )
            preferred_universes = st.multiselect("Preferred universes", UNIVERSE_OPTIONS, default=[x for x in profile.get("preferred_universes", []) if x in UNIVERSE_OPTIONS])
            if st.form_submit_button("Save Profile", width="stretch"):
                update_section("profile", {
                    "display_name": display_name.strip() or "Dee", "trading_style": trading_style,
                    "typical_hold_days": typical_hold_days, "preferred_setups": preferred_setups,
                    "preferred_sectors": preferred_sectors, "preferred_universes": preferred_universes,
                })
                st.session_state.momopro_settings = get_settings(); st.success("Profile saved."); st.rerun()

    with settings_tabs[1]:
        risk = settings["risk"]
        with st.form("settings_risk_form"):
            c1, c2, c3 = st.columns(3)
            account_size_setting = c1.number_input("Account size ($)", min_value=0.0, value=float(risk.get("account_size", 10000)), step=500.0)
            risk_per_trade = c2.number_input("Risk per trade (%)", 0.0, 100.0, float(risk.get("risk_per_trade_pct", 1)), 0.1)
            max_position_pct = c3.number_input("Maximum position size (%)", 0.0, 100.0, float(risk.get("max_position_pct", 25)), 1.0)
            c4, c5, c6 = st.columns(3)
            max_open_positions = c4.number_input("Maximum open positions", 1, 100, int(risk.get("max_open_positions", 5)))
            daily_loss = c5.number_input("Daily loss limit (%)", 0.0, 100.0, float(risk.get("daily_loss_limit_pct", 2)), 0.1)
            weekly_loss = c6.number_input("Weekly loss limit (%)", 0.0, 100.0, float(risk.get("weekly_loss_limit_pct", 5)), 0.1)
            minimum_rr = st.number_input("Minimum acceptable risk/reward", 0.0, 20.0, float(risk.get("minimum_rr", 2)), 0.1)
            stop_options = ["Structure / Support", "EMA21", "EMA50", "ATR", "Swing Low", "Manual"]
            stop_style = st.selectbox("Default stop style", stop_options, index=stop_options.index(risk.get("stop_style", "Structure / Support")) if risk.get("stop_style") in stop_options else 0)
            profit_options = ["Scale at T1 / T2 / T3", "Full exit at target", "Trail after T1", "Manual"]
            profit_style = st.selectbox("Partial-profit preference", profit_options, index=profit_options.index(risk.get("partial_profit_style", profit_options[0])) if risk.get("partial_profit_style") in profit_options else 0)
            if st.form_submit_button("Save Risk Settings", width="stretch"):
                update_section("risk", {
                    "account_size": account_size_setting, "risk_per_trade_pct": risk_per_trade,
                    "max_position_pct": max_position_pct, "max_open_positions": max_open_positions,
                    "daily_loss_limit_pct": daily_loss, "weekly_loss_limit_pct": weekly_loss,
                    "minimum_rr": minimum_rr, "stop_style": stop_style, "partial_profit_style": profit_style,
                })
                st.session_state.momopro_settings = get_settings(); st.success("Risk settings saved."); st.rerun()

    with settings_tabs[2]:
        scan = settings["scanner"]
        with st.form("settings_scanner_form"):
            a, b, c = st.columns(3)
            price_min = a.number_input("Minimum price ($)", 0.0, 100000.0, float(scan.get("price_min", 3)), 0.5)
            price_max = b.number_input("Maximum price ($)", 0.0, 100000.0, float(scan.get("price_max", 50)), 1.0)
            avg_volume = c.number_input("Minimum average volume", 0, 1000000000, int(scan.get("minimum_average_volume", 1000000)), 100000)
            d, e, f = st.columns(3)
            min_rvol = d.number_input("Minimum RVOL", 0.0, 100.0, float(scan.get("minimum_rvol", 1.1)), 0.1)
            min_atr = e.number_input("Minimum ATR %", 0.0, 100.0, float(scan.get("minimum_atr_pct", 4)), 0.25)
            max_extension = f.number_input("Maximum EMA21 extension %", 0.0, 100.0, float(scan.get("maximum_ema21_extension_pct", 6)), 0.5)
            g, h, i = st.columns(3)
            min_momo = g.number_input("Minimum Momo Score", 0, 100, int(scan.get("minimum_momo_score", 0)))
            grade_options = ["A+", "A", "B", "C", "D"]
            min_grade = h.selectbox("Minimum grade", grade_options, index=grade_options.index(scan.get("minimum_grade", "C")) if scan.get("minimum_grade") in grade_options else 3)
            result_limit = i.number_input("Maximum displayed results", 1, 1000, int(scan.get("result_limit", 100)))
            default_universe = st.selectbox("Default scanner universe", UNIVERSE_OPTIONS, index=UNIVERSE_OPTIONS.index(scan.get("default_universe", "Entire Market")) if scan.get("default_universe") in UNIVERSE_OPTIONS else 0)
            exclude_etfs = st.checkbox("Exclude ETFs/funds", value=bool(scan.get("exclude_etfs", True)))
            exclude_otc = st.checkbox("Exclude OTC securities", value=bool(scan.get("exclude_otc", True)))
            if st.form_submit_button("Save Scanner Settings", width="stretch"):
                if price_max < price_min: st.error("Maximum price must be at least the minimum price.")
                else:
                    update_section("scanner", {
                        "price_min": price_min, "price_max": price_max, "minimum_average_volume": avg_volume,
                        "minimum_rvol": min_rvol, "minimum_atr_pct": min_atr,
                        "maximum_ema21_extension_pct": max_extension, "minimum_momo_score": min_momo,
                        "minimum_grade": min_grade, "result_limit": result_limit, "default_universe": default_universe,
                        "exclude_etfs": exclude_etfs, "exclude_otc": exclude_otc,
                    })
                    st.session_state.momopro_settings = get_settings(); st.success("Scanner preferences saved."); st.rerun()

    with settings_tabs[3]:
        ind = settings["indicators"]
        with st.form("settings_indicators_form"):
            c1, c2, c3 = st.columns(3)
            ema_fast = c1.number_input("Fast EMA", 1, 500, int(ind.get("ema_fast", 21)))
            ema_mid = c2.number_input("Mid EMA", 1, 500, int(ind.get("ema_mid", 50)))
            ema_slow = c3.number_input("Slow EMA", 1, 1000, int(ind.get("ema_slow", 200)))
            c4, c5, c6 = st.columns(3)
            rsi_length = c4.number_input("RSI length", 2, 100, int(ind.get("rsi_length", 14)))
            atr_length = c5.number_input("ATR length", 2, 100, int(ind.get("atr_length", 14)))
            rvol_lookback = c6.number_input("RVOL lookback", 2, 250, int(ind.get("rvol_lookback", 20)))
            c7, c8, c9 = st.columns(3)
            macd_fast = c7.number_input("MACD fast", 1, 100, int(ind.get("macd_fast", 12)))
            macd_slow = c8.number_input("MACD slow", 2, 200, int(ind.get("macd_slow", 26)))
            macd_signal = c9.number_input("MACD signal", 1, 100, int(ind.get("macd_signal", 9)))
            primary_tf = st.selectbox("Primary timeframe", ["Daily", "4H", "1H", "15m"], index=["Daily", "4H", "1H", "15m"].index(ind.get("primary_timeframe", "Daily")))
            confirmation_tfs = st.multiselect("Confirmation timeframes", ["Weekly", "Daily", "4H", "1H", "15m", "5m"], default=ind.get("confirmation_timeframes", ["4H", "1H", "15m"]))
            if st.form_submit_button("Save Indicator Settings", width="stretch"):
                update_section("indicators", {
                    "ema_fast": ema_fast, "ema_mid": ema_mid, "ema_slow": ema_slow,
                    "rsi_length": rsi_length, "atr_length": atr_length, "rvol_lookback": rvol_lookback,
                    "macd_fast": macd_fast, "macd_slow": macd_slow, "macd_signal": macd_signal,
                    "primary_timeframe": primary_tf, "confirmation_timeframes": confirmation_tfs,
                })
                st.session_state.momopro_settings = get_settings(); st.success("Indicator preferences saved."); st.rerun()

    with settings_tabs[4]:
        ai = settings["ai"]
        with st.form("settings_ai_form"):
            style_options = ["Conservative", "Balanced", "Aggressive"]
            ai_style = st.selectbox("Analysis style", style_options, index=style_options.index(ai.get("analysis_style", "Balanced")))
            depth_options = ["Concise", "Detailed", "Deep Research"]
            response_depth = st.selectbox("Response depth", depth_options, index=depth_options.index(ai.get("response_depth", "Detailed")))
            challenge = st.checkbox("Challenge my thesis when evidence disagrees", value=bool(ai.get("challenge_thesis", True)))
            st.markdown("#### Evidence weights")
            cols = st.columns(5)
            tech_w = cols[0].number_input("Technicals", 0, 100, int(ai.get("technical_weight", 35)))
            market_w = cols[1].number_input("Market", 0, 100, int(ai.get("market_weight", 15)))
            news_w = cols[2].number_input("News", 0, 100, int(ai.get("news_weight", 20)))
            smart_w = cols[3].number_input("Smart Money", 0, 100, int(ai.get("smart_money_weight", 15)))
            hist_w = cols[4].number_input("Historical", 0, 100, int(ai.get("historical_weight", 15)))
            st.caption(f"Current total weight: {tech_w + market_w + news_w + smart_w + hist_w}%")
            t1, t2, t3 = st.columns(3)
            buy_threshold = t1.number_input("Buy threshold", 0, 100, int(ai.get("buy_threshold", 85)))
            watch_threshold = t2.number_input("Watch threshold", 0, 100, int(ai.get("watch_threshold", 70)))
            wait_threshold = t3.number_input("Wait threshold", 0, 100, int(ai.get("wait_threshold", 50)))
            if st.form_submit_button("Save AI Behavior", width="stretch"):
                if not (buy_threshold >= watch_threshold >= wait_threshold): st.error("Thresholds must descend: Buy ≥ Watch ≥ Wait.")
                elif tech_w + market_w + news_w + smart_w + hist_w != 100: st.error("AI evidence weights must total exactly 100%.")
                else:
                    update_section("ai", {
                        "analysis_style": ai_style, "response_depth": response_depth, "challenge_thesis": challenge,
                        "technical_weight": tech_w, "market_weight": market_w, "news_weight": news_w,
                        "smart_money_weight": smart_w, "historical_weight": hist_w,
                        "buy_threshold": buy_threshold, "watch_threshold": watch_threshold, "wait_threshold": wait_threshold,
                    })
                    st.session_state.momopro_settings = get_settings(); st.success("AI behavior saved."); st.rerun()

    with settings_tabs[5]:
        dash = settings["dashboard"]
        with st.form("settings_dashboard_form"):
            default_dash_universe = st.selectbox("Default universe", UNIVERSE_OPTIONS, index=UNIVERSE_OPTIONS.index(dash.get("default_universe", "Entire Market")) if dash.get("default_universe") in UNIVERSE_OPTIONS else 0)
            candidate_count = st.number_input("Scanner candidates shown", 1, 50, int(dash.get("candidate_count", 10)))
            morning_brief = st.checkbox("Show Today’s Trading Plan", value=bool(dash.get("morning_brief_enabled", True)))
            dashboard_toggles = {}
            labels = {
                "show_market_health": "Market health", "show_sector_leadership": "Sector leadership",
                "show_scanner_candidates": "Scanner candidates", "show_watchlist_alerts": "Watchlist alerts",
                "show_open_trades": "Open trades", "show_market_news": "Market news",
                "show_ai_recommendations": "Recent AI recommendations", "show_broker_status": "Broker status",
            }
            cols = st.columns(2)
            for idx, (key, label) in enumerate(labels.items()): dashboard_toggles[key] = cols[idx % 2].checkbox(label, value=bool(dash.get(key, True)), key=f"dash_setting_{key}")
            if st.form_submit_button("Save Dashboard Settings", width="stretch"):
                update_section("dashboard", {"default_universe": default_dash_universe, "candidate_count": candidate_count, "morning_brief_enabled": morning_brief, **dashboard_toggles})
                st.session_state.dashboard_universe = default_dash_universe
                st.session_state.momopro_settings = get_settings(); st.success("Dashboard preferences saved."); st.rerun()

    with settings_tabs[6]:
        journal = settings["journal"]; perf = settings["performance"]
        with st.form("settings_journal_performance_form"):
            st.markdown("#### Journal")
            c1, c2 = st.columns(2)
            default_direction = c1.selectbox("Default direction", ["Long", "Short"], index=0 if journal.get("default_direction", "Long") == "Long" else 1)
            default_broker = c2.selectbox("Default broker", ["Webull", "Manual / None", "Other"], index=["Webull", "Manual / None", "Other"].index(journal.get("default_broker", "Webull")) if journal.get("default_broker") in ["Webull", "Manual / None", "Other"] else 0)
            require_thesis = st.checkbox("Require an entry thesis", value=bool(journal.get("require_entry_thesis", True)))
            require_review = st.checkbox("Require post-trade review", value=bool(journal.get("require_exit_review", True)))
            save_screens = st.checkbox("Save chart screenshots", value=bool(journal.get("save_chart_screenshots", True)))
            st.markdown("#### Performance")
            perf_source = st.selectbox("Default source filter", SOURCE_OPTIONS, index=SOURCE_OPTIONS.index(perf.get("default_source_filter", "All Trades")) if perf.get("default_source_filter") in SOURCE_OPTIONS else 0)
            perf_period = st.selectbox("Default period", ["All Time", "Year to Date", "Last 12 Months", "Last 90 Days", "Last 30 Days"], index=0)
            pnl_display = st.selectbox("Default P/L display", ["Net P/L", "Gross P/L"], index=0 if perf.get("pnl_display", "Net P/L") == "Net P/L" else 1)
            show_fees = st.checkbox("Show fees", value=bool(perf.get("show_fees", True)))
            show_equity = st.checkbox("Show equity curve", value=bool(perf.get("show_equity_curve", True)))
            show_ai_acc = st.checkbox("Show AI accuracy", value=bool(perf.get("show_ai_accuracy", True)))
            show_discipline = st.checkbox("Show discipline metrics", value=bool(perf.get("show_discipline_metrics", True)))
            if st.form_submit_button("Save Journal & Performance Settings", width="stretch"):
                update_section("journal", {"default_direction": default_direction, "default_broker": default_broker, "require_entry_thesis": require_thesis, "require_exit_review": require_review, "save_chart_screenshots": save_screens})
                update_section("performance", {"default_source_filter": perf_source, "default_period": perf_period, "pnl_display": pnl_display, "show_fees": show_fees, "show_equity_curve": show_equity, "show_ai_accuracy": show_ai_acc, "show_discipline_metrics": show_discipline})
                st.session_state.momopro_settings = get_settings(); st.success("Journal and Performance preferences saved."); st.rerun()

    with settings_tabs[7]:
        alert_settings = settings["alerts"]
        with st.form("settings_alert_form"):
            cooldown_setting = st.number_input("Default alert cooldown (hours)", 0, 720, int(alert_settings.get("default_cooldown_hours", 24)))
            priority_options = ["Low", "Medium", "High", "Critical"]
            priority = st.selectbox("Minimum notification priority", priority_options, index=priority_options.index(alert_settings.get("minimum_priority", "Medium")))
            brief_alerts = st.checkbox("Include alert summary in Morning Brief", value=bool(alert_settings.get("morning_brief_alert_summary", True)))
            quiet_enabled = st.checkbox("Enable quiet hours", value=bool(alert_settings.get("quiet_hours_enabled", False)))
            q1, q2 = st.columns(2)
            quiet_start = q1.text_input("Quiet hours start (24h)", value=str(alert_settings.get("quiet_hours_start", "21:00")))
            quiet_end = q2.text_input("Quiet hours end (24h)", value=str(alert_settings.get("quiet_hours_end", "06:00")))
            if st.form_submit_button("Save Alert Settings", width="stretch"):
                update_section("alerts", {"default_cooldown_hours": cooldown_setting, "minimum_priority": priority, "morning_brief_alert_summary": brief_alerts, "quiet_hours_enabled": quiet_enabled, "quiet_hours_start": quiet_start, "quiet_hours_end": quiet_end})
                st.session_state.momopro_settings = get_settings(); st.success("Alert preferences saved."); st.rerun()

    with settings_tabs[8]:
        data = settings["data"]
        provider_rows = [
            {"Integration": "Alpaca Market Data", "Status": "Configured" if _secret("ALPACA_API_KEY") and _secret("ALPACA_SECRET_KEY") else "Missing secrets", "Role": "Market data"},
            {"Integration": "OpenAI", "Status": "Configured" if _secret("OPENAI_API_KEY") else "Missing secret", "Role": "AI research"},
            {"Integration": "Webull CSV", "Status": "Enabled" if data.get("webull_csv_enabled", True) else "Disabled", "Role": "Historical import"},
            {"Integration": "Webull OpenAPI", "Status": str(webull_connection_status().get("status", "Not Connected")).replace("_", " ").title(), "Role": "Official read-only daily sync"},
            {"Integration": "TradingView", "Status": data.get("tradingview_status", "Planned for v0.95"), "Role": "Execution ecosystem"},
        ]
        st.dataframe(pd.DataFrame(provider_rows), width="stretch", hide_index=True)
        with st.form("settings_data_form"):
            c1, c2, c3 = st.columns(3)
            market_cache = c1.number_input("Market cache (minutes)", 1, 1440, int(data.get("market_cache_minutes", 15)))
            news_cache = c2.number_input("News cache (minutes)", 1, 1440, int(data.get("news_cache_minutes", 15)))
            scanner_cache = c3.number_input("Scanner cache (minutes)", 1, 1440, int(data.get("scanner_cache_minutes", 30)))
            auto_refresh = st.checkbox("Auto-refresh Dashboard when supported", value=bool(data.get("auto_refresh_dashboard", False)))
            webull_csv = st.checkbox("Enable Webull CSV import", value=bool(data.get("webull_csv_enabled", True)))
            if st.form_submit_button("Save Data Preferences", width="stretch"):
                update_section("data", {"market_cache_minutes": market_cache, "news_cache_minutes": news_cache, "scanner_cache_minutes": scanner_cache, "auto_refresh_dashboard": auto_refresh, "webull_csv_enabled": webull_csv})
                st.session_state.momopro_settings = get_settings(); st.success("Data preferences saved."); st.rerun()

    with settings_tabs[9]:
        st.markdown("#### Current settings JSON")
        st.json(settings, expanded=False)
        export_payload = __import__("json").dumps(settings, indent=2)
        st.download_button("Download Settings Backup", export_payload, "momopro_settings.json", "application/json", width="stretch")
        uploaded_settings = st.file_uploader("Restore settings backup", type=["json"], key="settings_restore_upload")
        if uploaded_settings is not None and st.button("Restore Uploaded Settings", width="stretch"):
            try:
                restored = __import__("json").loads(uploaded_settings.getvalue().decode("utf-8"))
                save_settings(restored); st.session_state.momopro_settings = get_settings(); st.success("Settings restored."); st.rerun()
            except Exception as error:
                st.error(f"Could not restore settings: {error}")
        st.warning("Resetting restores MomoPro defaults. It does not delete trades, watchlists, alerts, AI reports, or broker history.")
        if st.button("Reset All Settings to Defaults", type="secondary", width="stretch"):
            reset_settings(); st.session_state.momopro_settings = get_settings(); st.session_state.dashboard_universe = get_setting("dashboard.default_universe", "Entire Market", st.session_state.momopro_settings); st.success("Settings reset."); st.rerun()


def _persist_live_chart_controls() -> None:
    persist_session_workspace()


# -----------------------------
# v0.95B — Native Live Chart & TradingView Bridge
# -----------------------------
if active_page_is("Live Chart"):
    st.header("Live Chart & TradingView Bridge")
    st.caption(
        "Review live market structure inside MomoPro, overlay the saved Official MomoPro Plan, "
        "and hand the exact same plan to your TradingView indicator."
    )

    saved_analyses = {item.symbol: item for item in list_analyses()}
    default_chart_symbol = str(
        st.session_state.get("live_chart_symbol")
        or st.session_state.get("selected_symbol")
        or "SPY"
    ).upper().strip()
    if not st.session_state.get("live_chart_symbol"):
        st.session_state.live_chart_symbol = default_chart_symbol
    controls = st.columns([2, 1, 1, 1])
    with controls[0]:
        chart_symbol = st.text_input(
            "Symbol", key="live_chart_symbol",
            on_change=sync_symbol_widget, args=("live_chart_symbol",),
        ).upper().strip()
    with controls[1]:
        chart_timeframe = st.selectbox("Timeframe", available_timeframes(), key="live_chart_timeframe", on_change=_persist_live_chart_controls)
    with controls[2]:
        chart_candles = st.selectbox("Candles", [100, 200, 300, 500], key="live_chart_candles", on_change=_persist_live_chart_controls)
    with controls[3]:
        refresh_chart = st.button("Refresh Chart", width="stretch", key="refresh_live_chart")

    with st.expander("Chart display controls", expanded=False):
        overlay_choices = st.multiselect(
            "Visible overlays",
            ["EMA21", "EMA50", "EMA200", "Entry", "Max Chase", "Stop", "T1", "T2", "T3", "Support", "Resistance", "RSI", "MACD", "RVOL"],
            default=["EMA21", "EMA50", "EMA200", "Entry", "Max Chase", "Stop", "T1", "T2", "T3", "Support", "Resistance", "RSI", "MACD", "RVOL"],
            key="live_chart_overlays",
            on_change=_persist_live_chart_controls,
            help="Turn off any plan level or indicator panel that is crowding the chart. Level details remain available through hoverable symbols.",
        )
    chart_display_options = {
        "ema21": "EMA21" in overlay_choices,
        "ema50": "EMA50" in overlay_choices,
        "ema200": "EMA200" in overlay_choices,
        "entry": "Entry" in overlay_choices,
        "max_chase": "Max Chase" in overlay_choices,
        "stop": "Stop" in overlay_choices,
        "t1": "T1" in overlay_choices,
        "t2": "T2" in overlay_choices,
        "t3": "T3" in overlay_choices,
        "support": "Support" in overlay_choices,
        "resistance": "Resistance" in overlay_choices,
        "rsi": "RSI" in overlay_choices,
        "macd": "MACD" in overlay_choices,
        "rvol": "RVOL" in overlay_choices,
    }

    analysis = saved_analyses.get(chart_symbol) or get_analysis(chart_symbol)
    plan = analysis.plan.__dict__ if analysis else {}

    if analysis:
        plan_cols = st.columns(7)
        plan_cols[0].metric("Setup", analysis.setup or "—")
        plan_cols[1].metric("Grade", analysis.grade or "—")
        plan_cols[2].metric("Momo Score", "—" if analysis.momo_score is None else f"{analysis.momo_score:.0f}")
        plan_cols[3].metric("Opportunity", "—" if analysis.opportunity_score is None else f"{analysis.opportunity_score:.0f}")
        plan_cols[4].metric("AI Confidence", "—" if analysis.ai_confidence is None else f"{analysis.ai_confidence:.0f}%")
        plan_cols[5].metric("Official Entry", money_text(plan.get("reference_entry") or plan.get("entry_low")))
        plan_cols[6].metric("Official Stop", money_text(plan.get("stop")))
    else:
        st.info("No saved Official MomoPro Plan exists for this ticker yet. The chart will still load without plan overlays.")

    cache_key = f"chart::{chart_symbol}::{chart_timeframe}::{chart_candles}"
    if refresh_chart:
        st.session_state.pop(cache_key, None)
    frame = st.session_state.get(cache_key)
    if chart_symbol and frame is None:
        with st.spinner(f"Loading {chart_symbol} {chart_timeframe} chart..."):
            try:
                frame = load_chart_bars(
                    st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_SECRET_KEY"],
                    chart_symbol, chart_timeframe, chart_candles,
                )
                st.session_state[cache_key] = frame
            except Exception as error:
                st.error(f"Chart data could not be loaded: {error}")
                frame = pd.DataFrame()

    if frame is not None and not frame.empty:
        latest = latest_chart_snapshot(frame)
        snapshot_cols = st.columns(6)
        snapshot_cols[0].metric("Last", money_text(latest.get("close")))
        snapshot_cols[1].metric("EMA21", money_text(latest.get("ema21")))
        snapshot_cols[2].metric("EMA50", money_text(latest.get("ema50")))
        snapshot_cols[3].metric("EMA200", money_text(latest.get("ema200")))
        snapshot_cols[4].metric("RSI", "—" if latest.get("rsi14") is None else f"{latest['rsi14']:.1f}")
        snapshot_cols[5].metric("RVOL", "—" if latest.get("rvol") is None else f"{latest['rvol']:.2f}x")
        st.plotly_chart(
            build_live_chart(frame, chart_symbol, chart_timeframe, plan, chart_display_options),
            width="stretch",
            config={
                "displaylogo": False,
                "scrollZoom": True,
                "responsive": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            },
        )
        st.caption(f"Latest available candle: {latest.get('timestamp') or 'Unavailable'} · Alpaca IEX feed")

    st.divider()
    st.subheader("TradingView Bridge")
    if not analysis:
        st.warning("Open the ticker in the Stock Report and generate its Official MomoPro Plan before exporting it to TradingView.")
    else:
        tv_payload = build_tradingview_payload(analysis, chart_timeframe)
        bridge_cols = st.columns([1, 1, 1])
        with bridge_cols[0]:
            st.link_button("Open in TradingView", tradingview_chart_url(chart_symbol, chart_timeframe), width="stretch")
        with bridge_cols[1]:
            st.download_button(
                "Download Official Plan JSON", payload_json(tv_payload),
                file_name=f"momopro_{chart_symbol}_{tv_payload['trade_id']}.json",
                mime="application/json", width="stretch",
            )
        with bridge_cols[2]:
            st.download_button(
                "Download Pine Input Block", pine_input_block(tv_payload),
                file_name=f"momopro_{chart_symbol}_pine_inputs.txt",
                mime="text/plain", width="stretch",
            )

        export_tabs = st.tabs(["Official Plan", "Official Plan Mode", "JSON Payload"])
        with export_tabs[0]:
            official = pd.DataFrame([
                {"Field": "Trade ID", "Value": tv_payload.get("trade_id")},
                {"Field": "Symbol", "Value": tv_payload.get("symbol")},
                {"Field": "Timeframe", "Value": tv_payload.get("timeframe")},
                {"Field": "Entry Low", "Value": tv_payload.get("entry_low")},
                {"Field": "Entry High", "Value": tv_payload.get("entry_high")},
                {"Field": "Reference Entry", "Value": tv_payload.get("reference_entry")},
                {"Field": "Maximum Chase", "Value": tv_payload.get("max_chase")},
                {"Field": "Stop", "Value": tv_payload.get("stop")},
                {"Field": "T1", "Value": tv_payload.get("t1")},
                {"Field": "T2", "Value": tv_payload.get("t2")},
                {"Field": "T3", "Value": tv_payload.get("t3")},
                {"Field": "Setup", "Value": tv_payload.get("setup")},
                {"Field": "Grade", "Value": tv_payload.get("grade")},
                {"Field": "AI Confidence", "Value": tv_payload.get("ai_confidence")},
            ])
            st.dataframe(official, hide_index=True, width="stretch")
            if analysis.thesis:
                st.markdown("**Trade thesis**")
                st.write(analysis.thesis)
            if analysis.invalidation:
                st.markdown("**Invalidation**")
                st.write(analysis.invalidation)
        with export_tabs[1]:
            packet = official_plan_packet(tv_payload)
            diagnostics = packet_diagnostics(packet)
            st.markdown("**Step 1 — Copy only the packet below**")
            st.text_area(
                "Official Plan Packet",
                value=packet,
                height=90,
                key=f"official_plan_packet_{chart_symbol}_{chart_timeframe}",
                help="Click inside, press Ctrl+A, then Ctrl+C. Paste this exact one-line value into the MomoPro Official Plan Validation settings.",
            )
            if diagnostics["valid"]:
                st.success(f"Packet ready: {diagnostics['field_count']} of {diagnostics['expected_field_count']} required fields detected.")
            else:
                st.error("The packet is not ready: " + " ".join(diagnostics["errors"]))
            st.markdown("**Step 2 — TradingView Official Plan Mode settings**")
            st.code(
                "1. Add MomoPro Official Plan Validation to the same chart as your original MomoPro indicator.\n"
                "2. Open the Official Plan Validation gear icon → Inputs.\n"
                "3. Turn ON Enable Official Plan Mode.\n"
                "4. Paste the one-line packet into Official Plan Packet.\n"
                "5. Leave Validate Timeframe OFF for the first test.\n"
                "6. Click OK.",
                language="text",
            )
            with st.expander("Full instruction block (the companion can also extract the packet from this)"):
                st.code(pine_input_block(tv_payload), language="text")
            st.caption("Your original MomoPro indicator remains unchanged. The validation layer reads the official strategic plan while your original MomoPro indicator keeps all of its normal signals, visuals, lifecycle, and exit logic active.")
        with export_tabs[2]:
            st.code(payload_json(tv_payload), language="json")

    st.info(
        "The Live Chart is MomoPro's research chart. Your full TradingView indicator remains the execution and trade-management companion. "
        "The original MomoPro indicator remains unchanged. The Official Plan indicator and this research chart now use hover-first visuals and independent display controls to reduce clutter."
    )


# Persist lightweight workspace state on every successful rerun. Navigation
# callbacks also save immediately before any st.rerun().
persist_session_workspace()


# v0.98.3 non-blocking loader worker. Keep this as the final rendered element.
render_automatic_loading_worker()

import math

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

from watchlist_manager import (
    add_symbols, create_watchlist, delete_watchlist, get_symbols,
    get_watchlist_item, list_watchlists, remove_symbol, rename_watchlist,
    update_watchlist_item,
)
from watchlist_ai import build_morning_brief, refresh_item_from_scan
from watchlist_models import WatchlistItem, utc_now
from alert_engine import (
    clear_events, create_rule, delete_rule, evaluate_alerts, load_alerts,
    mark_event_read, set_rule_enabled,
)
from alert_rules import RULE_TYPES


st.set_page_config(
    page_title="MomoPro AI",
    page_icon="📈",
    layout="wide",
)

st.title("📈 MomoPro AI")
st.subheader(
    "Your AI Swing Trading Partner"
)


def valid_value(value):
    return (
        value is not None
        and not pd.isna(value)
        and (
            not isinstance(value, float)
            or math.isfinite(value)
        )
    )


def money_text(value):
    if not valid_value(value):
        return "—"

    return f"${float(value):.2f}"


def percent_text(value):
    if not valid_value(value):
        return "—"

    return f"{float(value):.2f}%"


def r_text(value):
    if not valid_value(value):
        return "—"

    return f"{float(value):.2f}R"



def compact_number(value):
    if not valid_value(value):
        return "—"
    number = float(value)
    absolute = abs(number)
    if absolute >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    if absolute >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{number / 1_000:.1f}K"
    return f"{number:,.0f}"


def reaction_text(
    quality,
    touches,
):
    if not valid_value(touches):
        return None

    quality_text = (
        str(quality)
        if valid_value(quality)
        else "Unrated"
    )

    touch_count = int(float(touches))

    reaction_word = (
        "reaction"
        if touch_count == 1
        else "reactions"
    )

    return (
        f"{quality_text} · "
        f"{touch_count} confirmed "
        f"{reaction_word}"
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_relative_strength(symbol):
    return get_relative_strength(
        st.secrets["ALPACA_API_KEY"],
        st.secrets["ALPACA_SECRET_KEY"],
        symbol,
    )


def _secret(name):
    try:
        return st.secrets.get(name)
    except Exception:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def load_market_news():
    return get_market_news(
        st.secrets["ALPACA_API_KEY"],
        st.secrets["ALPACA_SECRET_KEY"],
        alpha_vantage_api_key=_secret("ALPHA_VANTAGE_API_KEY"),
        finnhub_api_key=_secret("FINNHUB_API_KEY"),
        fmp_api_key=_secret("FMP_API_KEY"),
    )


@st.cache_data(ttl=900, show_spinner=False)
def load_ticker_news(symbol):
    return get_ticker_news(
        st.secrets["ALPACA_API_KEY"],
        st.secrets["ALPACA_SECRET_KEY"],
        symbol,
        alpha_vantage_api_key=_secret("ALPHA_VANTAGE_API_KEY"),
        finnhub_api_key=_secret("FINNHUB_API_KEY"),
        fmp_api_key=_secret("FMP_API_KEY"),
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_sec_filings(symbol):
    return get_recent_filings(symbol)


@st.cache_data(ttl=3600, show_spinner=False)
def load_fda_records(company_name):
    return get_fda_enforcement(company_name)


@st.cache_data(ttl=1800, show_spinner=False)
def load_smart_money(symbol):
    return get_smart_money_intelligence(
        symbol=symbol,
        alpaca_api_key=st.secrets["ALPACA_API_KEY"],
        alpaca_secret_key=st.secrets["ALPACA_SECRET_KEY"],
        alpha_vantage_api_key=_secret("ALPHA_VANTAGE_API_KEY"),
        finnhub_api_key=_secret("FINNHUB_API_KEY"),
        fmp_api_key=_secret("FMP_API_KEY"),
    )


@st.cache_data(ttl=1800, show_spinner=False)
def load_trade_intelligence(symbol, stock_payload):
    return get_trade_intelligence(
        api_key=st.secrets["ALPACA_API_KEY"],
        secret_key=st.secrets["ALPACA_SECRET_KEY"],
        symbol=symbol,
        stock=stock_payload,
    )


@st.cache_data(ttl=1800, show_spinner=False)
def load_comparison_research(query):
    return research_comparison(
        query=query,
        alpaca_api_key=st.secrets["ALPACA_API_KEY"],
        alpaca_secret_key=st.secrets["ALPACA_SECRET_KEY"],
        alpha_vantage_api_key=_secret("ALPHA_VANTAGE_API_KEY"),
        finnhub_api_key=_secret("FINNHUB_API_KEY"),
        fmp_api_key=_secret("FMP_API_KEY"),
    )


if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None

if "ai_commentary_cache" not in st.session_state:
    st.session_state.ai_commentary_cache = {}

if "market_context" not in st.session_state:
    st.session_state.market_context = None

if "news_ai_cache" not in st.session_state:
    st.session_state.news_ai_cache = {}

if "news_search_symbol" not in st.session_state:
    st.session_state.news_search_symbol = ""

if "smart_money_cache" not in st.session_state:
    st.session_state.smart_money_cache = {}

if "trade_intelligence_cache" not in st.session_state:
    st.session_state.trade_intelligence_cache = {}

if "trade_plan_prefill" not in st.session_state:
    st.session_state.trade_plan_prefill = {}

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


tabs = st.tabs(
    [
        "Dashboard",
        "Market Context",
        "Scanner",
        "News",
        "AI Analysis",
        "Watchlist",
        "Trade Planner",
        "Journal",
        "Performance",
        "Settings",
    ]
)


# -----------------------------
# Dashboard
# -----------------------------
with tabs[0]:
    st.header("Dashboard")

    if st.button(
        "Test Alpaca Connection",
        key="test_alpaca",
    ):
        (
            success,
            status,
            buying_power,
        ) = test_alpaca_connection()

        if success:
            st.success(
                "✅ Alpaca connected "
                "successfully!"
            )

            st.write(
                f"Account status: {status}"
            )

            st.write(
                f"Buying power: "
                f"${buying_power}"
            )

        else:
            st.error(
                "❌ Alpaca connection failed."
            )

            st.write(status)


    st.divider()
    st.subheader("Market Snapshot")
    dashboard_market = st.session_state.market_context
    if dashboard_market:
        snap = st.columns(6)
        snap[0].metric("Market Score", dashboard_market.get("market_score", "—"))
        snap[1].metric("Trend", dashboard_market.get("market_trend", "—"))
        snap[2].metric("Risk Environment", dashboard_market.get("risk_environment", "—"))
        dash_breadth = dashboard_market.get("breadth", {})
        snap[3].metric(
            "Breadth",
            dash_breadth.get("breadth_status", "—"),
            (
                f'{dash_breadth.get("breadth_score")}/100'
                if dash_breadth.get("breadth_score") is not None
                else None
            ),
        )
        dash_sentiment = dashboard_market.get("sentiment", {})
        snap[4].metric(
            "Sentiment",
            dash_sentiment.get("fear_greed_label", "—"),
            (
                f'{dash_sentiment.get("fear_greed_score")}/100'
                if dash_sentiment.get("fear_greed_score") is not None
                else None
            ),
        )
        dash_sectors = dashboard_market.get("sectors", {})
        top_sector = (dash_sectors.get("leaders") or [{}])[0]
        snap[5].metric(
            "Top Sector",
            top_sector.get("sector", "—"),
            (
                f'{top_sector.get("score")}/100'
                if top_sector.get("score") is not None
                else None
            ),
        )
        st.caption(dashboard_market.get("summary", ""))
        rotation = dashboard_market.get("sectors", {}).get("rotation_regime")
        sentiment_warning = dashboard_market.get("sentiment", {}).get("warning")
        if rotation:
            st.write(f"**Sector rotation:** {rotation}")
        if sentiment_warning:
            st.warning(sentiment_warning)
    else:
        st.caption("Open Market Context and refresh it to populate today’s snapshot.")


    st.divider()
    st.subheader("Top Market Headlines")
    try:
        dashboard_news = rank_news(load_market_news())[:5]
        if dashboard_news:
            for item in dashboard_news:
                label = f'{item.get("impact", "—")} impact · {item.get("sentiment", "Neutral")}'
                if item.get("url"):
                    st.markdown(f'**[{item.get("headline")}]({item.get("url")})**')
                else:
                    st.markdown(f'**{item.get("headline")}**')
                st.caption(label)
        else:
            st.caption("No recent market headlines were returned.")
    except Exception as error:
        st.caption(f"Market headlines are temporarily unavailable: {error}")


# -----------------------------
# Market Context
# -----------------------------
with tabs[1]:
    st.header("Market Context")
    st.caption(
        "Full broad-market assessment. Refresh this before scanning "
        "when you want the latest market backdrop."
    )

    if st.button(
        "Load / Refresh Market Context",
        key="refresh_market_context",
    ):
        try:
            with st.spinner("Analyzing the broad market and breadth..."):
                st.session_state.market_context = get_market_context(
                    st.secrets["ALPACA_API_KEY"],
                    st.secrets["ALPACA_SECRET_KEY"],
                )
        except Exception as error:
            st.error(f"Market context could not be loaded: {error}")

    market = st.session_state.market_context

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
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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
                use_container_width=True,
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
            use_container_width=True,
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
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "Positive values indicate outperformance versus SPY; negative "
                "values indicate lagging performance over the same period."
            )
        else:
            st.caption("Sector relative-strength leadership is unavailable.")
    else:
        st.info("Load Market Context to see the complete market assessment.")


# -----------------------------
# Scanner
# -----------------------------
with tabs[2]:
    st.header("Scanner")

    if st.button(
        "Run Market Scan",
        key="run_market_scan",
    ):
        with st.spinner(
            "Scanning market..."
        ):
            st.session_state.scan_results = (
                run_scan()
            )

        st.session_state.selected_symbol = (
            None
        )

    df = st.session_state.scan_results

    if df is not None and not df.empty:
        st.success(
            f"Scan complete! "
            f"{len(df)} stocks analyzed."
        )

        st.caption(
            "Click a row to open its "
            "Stock Report."
        )

        hidden_columns = {
            "Momo Confidence": None,
            "Confidence Rating": None,
            "Trend Confidence": None,
            "Location Confidence": None,
            "Momentum Confidence": None,
            "Volume Confidence": None,
            "Opportunity Confidence": None,
            "Risk Confidence": None,
            "Structure Confidence": None,

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

            st.session_state.selected_symbol = (
                selected_row["Symbol"]
            )

        selected_symbol = (
            st.session_state
            .selected_symbol
        )

        if selected_symbol:
            selected_stock = df[
                df["Symbol"]
                == selected_symbol
            ].iloc[0]

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

            with header_right:
                if st.button(
                    "Close Report",
                    key=(
                        "close_stock_report"
                    ),
                ):
                    (
                        st.session_state
                        .selected_symbol
                    ) = None

                    st.rerun()

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
                "Load / Refresh Relative Strength",
                key=f"relative_strength_{selected_symbol}",
            )

            if rs_refresh:
                load_relative_strength.clear()

            with st.spinner("Comparing the stock with market benchmarks..."):
                relative_strength = load_relative_strength(selected_symbol)

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
                    use_container_width=True,
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
                "Load / Refresh Smart Money",
                key=f"smart_money_{selected_symbol}",
            )
            if smart_refresh:
                load_smart_money.clear()
                st.session_state.smart_money_cache.pop(selected_symbol, None)

            smart_money_context = st.session_state.smart_money_cache.get(selected_symbol)
            if smart_refresh:
                with st.spinner(f"Loading Smart Money data for {selected_symbol}..."):
                    try:
                        smart_money_context = load_smart_money(selected_symbol)
                    except Exception:
                        smart_money_context = {
                            "status": "Unavailable",
                            "overall_score": None,
                            "verdict": "Unavailable",
                            "read_status": "Unavailable",
                            "coverage_pct": 0,
                            "available_modules": 0,
                            "total_modules": 5,
                            "summary": "Smart Money data could not be loaded from the connected providers.",
                        }
                    st.session_state.smart_money_cache[selected_symbol] = smart_money_context

            if smart_money_context is None:
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
                    "summary": "Click Load / Refresh Smart Money to query the connected providers for this ticker.",
                    "data_note": "Smart Money is loaded on demand to conserve free API limits.",
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
                        st.dataframe(pd.DataFrame(active_contracts), use_container_width=True, hide_index=True)
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
                        st.dataframe(pd.DataFrame(transactions), use_container_width=True, hide_index=True)
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
                "Load / Refresh Trading Intelligence",
                key=f"trade_intelligence_{selected_symbol}",
            )
            if trade_refresh:
                load_trade_intelligence.clear()
                st.session_state.trade_intelligence_cache.pop(selected_symbol, None)

            trade_intelligence_context = st.session_state.trade_intelligence_cache.get(selected_symbol)
            if trade_refresh:
                with st.spinner(f"Analyzing trading structure for {selected_symbol}..."):
                    try:
                        trade_intelligence_context = load_trade_intelligence(
                            selected_symbol, selected_stock.to_dict()
                        )
                    except Exception:
                        trade_intelligence_context = {
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
                    st.session_state.trade_intelligence_cache[selected_symbol] = trade_intelligence_context

            if trade_intelligence_context is None:
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
                    st.dataframe(pd.DataFrame(patterns), use_container_width=True, hide_index=True)
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
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

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
                    st.dataframe(pd.DataFrame(target_rows), use_container_width=True, hide_index=True)
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
                    st.session_state.trade_plan_prefill = {
                        "symbol": selected_symbol,
                        "entry": selected_stock.get("Reference Entry") or selected_stock.get("Close"),
                        "stop": stop_data.get("standard") or selected_stock.get("Risk Reference"),
                        "t1": (trade_intelligence_context.get("targets", {}).get("targets", [{}])[0] or {}).get("price"),
                        "t2": (trade_intelligence_context.get("targets", {}).get("targets", [{}, {}])[1] or {}).get("price") if len(trade_intelligence_context.get("targets", {}).get("targets", [])) > 1 else None,
                        "t3": (trade_intelligence_context.get("targets", {}).get("targets", [{}, {}, {}])[2] or {}).get("price") if len(trade_intelligence_context.get("targets", {}).get("targets", [])) > 2 else None,
                    }
                    st.success("Trade plan loaded into the Trade Planner tab.")

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
                    use_container_width=True,
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
with tabs[3]:
    st.header("News")
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

        try:
            market_news = rank_news(load_market_news())
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
                    use_container_width=True,
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
with tabs[4]:
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
            use_container_width=True,
        )

    global_controls = st.columns([1, 3])
    with global_controls[0]:
        if st.button(
            "Clear Global Chat",
            key="clear_global_ai_chat",
            use_container_width=True,
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
            analysis_stock_payload = analysis_stock.to_dict()
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
                use_container_width=True,
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
                        st.success("Independent AI research completed.")
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
                        use_container_width=True,
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
                            use_container_width=True,
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
                use_container_width=True,
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
with tabs[5]:
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

    action_cols = st.columns([1, 1, 2])
    if action_cols[0].button("Refresh Intelligence", key="refresh_watchlist_intelligence", disabled=not items):
        refreshed = 0
        for item in items:
            row = scan_lookup.get(item.symbol)
            if row:
                refresh_item_from_scan(item, row); update_watchlist_item(item); refreshed += 1
        st.success(f"Refreshed {refreshed} watchlist profile(s) from the latest scanner results.")
        st.rerun()
    if action_cols[1].button("Evaluate Alerts", key="evaluate_watchlist_alerts", disabled=not items):
        fired = evaluate_alerts({item.symbol: item for item in items})
        for item in items: update_watchlist_item(item)
        st.success(f"{len(fired)} alert(s) triggered.") if fired else st.info("No alert conditions are currently met.")
        st.rerun()
    action_cols[2].caption("Run the scanner first for fresh technical values, then refresh intelligence.")

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
            priority_rows.append({"Priority": rank, "Symbol": item.symbol, "Grade": item.technical.get("grade", "—"), "AI Confidence": item.technical.get("confidence", "—"), "Opportunity": item.ai_state.get("opportunity_score", "—"), "AI Status": item.ai_state.get("thesis_status", "Not evaluated"), "Why Now": item.ai_state.get("opportunity_reason", "Run refresh intelligence.")})
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
            header_cols[3].metric("AI Confidence", tech.get("confidence", "—"))
            header_cols[4].metric("Opportunity", ai.get("opportunity_score", "—"))
            header_cols[5].metric("Price", money_text(tech.get("price")))
            st.caption(ai.get("opportunity_reason", "Run Refresh Intelligence after a scanner run to calculate Opportunity Score."))

            identity_tab, thesis_tab, timeline_tab, research_tab = st.tabs(["Profile", "AI Thesis Tracker", "Timeline", "Research History"])
            with identity_tab:
                c1, c2 = st.columns(2)
                item.company = c1.text_input("Company", value=item.company, key=f"company_{item.symbol}")
                item.sector = c2.text_input("Sector", value=item.sector, key=f"sector_{item.symbol}")
                item.industry = c1.text_input("Industry", value=item.industry, key=f"industry_{item.symbol}")
                tags_text = c2.text_input("Tags", value=", ".join(item.tags), key=f"tags_{item.symbol}")
                item.tags = [x.strip() for x in tags_text.split(",") if x.strip()]
                st.markdown("#### Technical Snapshot")
                st.json(tech if tech else {"status": "Refresh intelligence after running the scanner."}, expanded=False)
                st.markdown("#### Intelligence Snapshot")
                st.json(item.intelligence if item.intelligence else {"status": "No intelligence snapshot saved yet."}, expanded=False)
                if st.button("Save profile", key=f"save_profile_{item.symbol}"):
                    update_watchlist_item(item); st.success("Profile saved.")

            with thesis_tab:
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
                        st.write(snap.get("content", "")); st.caption(f"Opportunity then: {snap.get('ai_state',{}).get('opportunity_score','—')} · Confidence then: {snap.get('technical',{}).get('confidence','—')}")

            quick = st.columns(5)
            if quick[0].button("Open Stock Report", key=f"quick_report_{item.symbol}"):
                st.session_state.selected_symbol = item.symbol; st.info("Ticker loaded as the selected scanner stock. Open the Scanner tab.")
            if quick[1].button("Trade Planner", key=f"quick_plan_{item.symbol}"):
                st.session_state.trade_plan_prefill = {"symbol": item.symbol, "entry": item.entry_idea or tech.get("price"), "stop": item.stop, "t1": item.target}; st.success("Loaded into Trade Planner.")
            if quick[2].button("AI Research", key=f"quick_ai_{item.symbol}"):
                st.session_state.ai_analysis_symbol = item.symbol; st.info("Ticker loaded for AI Analysis.")
            if quick[3].button("News", key=f"quick_news_{item.symbol}"):
                st.session_state.news_search_symbol = item.symbol; st.info("Ticker loaded for News.")
            if quick[4].button("Remove", key=f"quick_remove_{item.symbol}"):
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
with tabs[6]:
    st.header("Trade Planner")
    st.caption("Build a custom trade plan while keeping the objective engine plan separate.")

    prefill = st.session_state.trade_plan_prefill or {}
    planner_symbol = st.text_input("Ticker", value=str(prefill.get("symbol", "")), key="planner_symbol").upper().strip()
    account_size = st.number_input(
        "Account Size ($)",
        min_value=0.0,
        value=10000.0,
        step=500.0,
        key="planner_account_size",
    )

    risk_pct = st.number_input(
        "Risk Per Trade (%)",
        min_value=0.0,
        max_value=100.0,
        value=1.0,
        step=0.1,
        format="%.2f",
        key="planner_risk_pct",
        help=(
            "Type any value from 0% to 100%. Press Enter or click outside "
            "the field to apply it."
        ),
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
        reward = target - entry if target > entry > 0 else None
        r_multiple = reward / risk_per_share if reward is not None and risk_per_share and risk_per_share > 0 else None
        rr_rows.append({"Target": name, "Price": target if target > 0 else None, "Reward / Share": round(reward, 2) if reward is not None else None, "R Multiple": round(r_multiple, 2) if r_multiple is not None else None})
    st.dataframe(pd.DataFrame(rr_rows), use_container_width=True, hide_index=True)

    st.markdown("### Plan Notes")
    plan_notes = st.text_area("Trade Thesis / Confirmation / Invalidation", key="trade_plan_notes")
    if st.button("Save Plan to Session", use_container_width=True):
        st.session_state.trade_plan_prefill = {"symbol": planner_symbol, "entry": entry, "stop": stop, "t1": t1, "t2": t2, "t3": t3, "notes": plan_notes}
        st.success("Trade plan saved in this session. Journal persistence comes in v0.8.")


# -----------------------------
# Journal
# -----------------------------
with tabs[7]:
    st.header("Journal")

    st.write(
        "Trade journal will appear here."
    )


# -----------------------------
# Performance
# -----------------------------
with tabs[8]:
    st.header("Performance")

    st.write(
        "Your stats will appear here."
    )


# -----------------------------
# Settings
# -----------------------------
with tabs[9]:
    st.header("Settings")

    st.write(
        "Strategy settings will appear here."
    )

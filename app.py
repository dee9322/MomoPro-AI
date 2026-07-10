import math

import pandas as pd
import streamlit as st

from ai_commentary import (
    build_momo_engine_decision,
    generate_ai_decision,
)
from alpaca_test import (
    test_alpaca_connection,
)
from scanner import run_scan
from market_context import get_market_context


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


if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None

if "ai_commentary_cache" not in st.session_state:
    st.session_state.ai_commentary_cache = {}

if "market_context" not in st.session_state:
    st.session_state.market_context = None


tabs = st.tabs(
    [
        "Dashboard",
        "Market Context",
        "Scanner",
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
    else:
        st.caption("Open Market Context and refresh it to populate today’s snapshot.")


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
            # Momo Engine Confidence
            # -------------------------
            st.divider()

            st.subheader(
                "Momo Engine Confidence"
            )

            confidence_columns = st.columns(2)

            confidence_columns[0].metric(
                "Confidence",
                percent_text(
                    selected_stock.get(
                        "Momo Confidence"
                    )
                ),
            )

            confidence_columns[1].metric(
                "Rating",
                selected_stock.get(
                    "Confidence Rating",
                    "—",
                ),
            )

            st.caption(
                "This is the rule-based Momo Engine confidence, "
                "separate from the independent AI Confidence that "
                "will be added later."
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
            # Engine and AI Decisions
            # -------------------------
            st.divider()

            st.subheader("Decision Center")

            engine_decision = build_momo_engine_decision(
                selected_stock
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
                    "For now, the AI uses the technical and structural "
                    "data already in this report. News, filings, options, "
                    "sector, and market feeds will be added in their "
                    "scheduled roadmap steps."
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
                "Momo Engine Confidence is now active. "
                "The next roadmap item is AI Commentary."
            )

    elif df is not None:
        st.warning(
            "The scan completed, but no "
            "qualifying stocks were found."
        )


# -----------------------------
# AI Analysis
# -----------------------------
with tabs[3]:
    st.header("AI Analysis")

    st.write(
        "AI breakdowns will appear here."
    )


# -----------------------------
# Watchlist
# -----------------------------
with tabs[4]:
    st.header("Watchlist")

    st.write(
        "Saved stocks will appear here."
    )


# -----------------------------
# Trade Planner
# -----------------------------
with tabs[5]:
    st.header("Trade Planner")
    st.write("Interactive trade planning will be built in its scheduled roadmap phase.")


# -----------------------------
# Journal
# -----------------------------
with tabs[6]:
    st.header("Journal")

    st.write(
        "Trade journal will appear here."
    )


# -----------------------------
# Performance
# -----------------------------
with tabs[7]:
    st.header("Performance")

    st.write(
        "Your stats will appear here."
    )


# -----------------------------
# Settings
# -----------------------------
with tabs[8]:
    st.header("Settings")

    st.write(
        "Strategy settings will appear here."
    )

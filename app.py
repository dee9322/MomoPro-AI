import math

import pandas as pd
import streamlit as st

from alpaca_test import test_alpaca_connection
from scanner import run_scan


st.set_page_config(
    page_title="MomoPro AI",
    page_icon="📈",
    layout="wide",
)

st.title("📈 MomoPro AI")
st.subheader("Your AI Swing Trading Partner")


def valid_value(value):
    return (
        value is not None
        and not pd.isna(value)
        and (
            not isinstance(value, float)
            or math.isfinite(value)
        )
    )


if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None


tabs = st.tabs(
    [
        "Dashboard",
        "Scanner",
        "AI Analysis",
        "Watchlist",
        "Journal",
        "Performance",
        "Settings",
    ]
)


with tabs[0]:
    st.header("Dashboard")

    if st.button("Test Alpaca Connection", key="test_alpaca"):
        success, status, buying_power = test_alpaca_connection()

        if success:
            st.success("✅ Alpaca connected successfully!")
            st.write(f"Account status: {status}")
            st.write(f"Buying power: ${buying_power}")
        else:
            st.error("❌ Alpaca connection failed.")
            st.write(status)


with tabs[1]:
    st.header("Scanner")

    if st.button("Run Market Scan", key="run_market_scan"):
        with st.spinner("Scanning market..."):
            st.session_state.scan_results = run_scan()

        st.session_state.selected_symbol = None

    df = st.session_state.scan_results

    if df is not None and not df.empty:
        st.success(f"Scan complete! {len(df)} stocks analyzed.")
        st.caption("Click a row to open its Stock Report.")

        hidden_columns = {
            "Support 1": None,
            "Support 2": None,
            "Support 3": None,
            "Resistance 1": None,
            "Resistance 2": None,
            "Resistance 3": None,
            "Reference Entry": None,
            "Risk Reference": None,
            "Reward Reference": None,
            "Risk Per Share": None,
            "Reward Per Share": None,
            "Risk Reward": None,
            "Risk Reward Status": None,
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

        selected_rows = table_event.selection.rows

        if selected_rows:
            selected_index = selected_rows[0]
            selected_row = df.iloc[selected_index]
            st.session_state.selected_symbol = selected_row["Symbol"]

        selected_symbol = st.session_state.selected_symbol

        if selected_symbol:
            selected_stock = df[
                df["Symbol"] == selected_symbol
            ].iloc[0]

            st.divider()

            header_left, header_right = st.columns([4, 1])

            with header_left:
                st.header(f"{selected_symbol} Stock Report")
                st.caption(
                    "MomoPro AI structural swing-trade analysis."
                )

            with header_right:
                if st.button(
                    "Close Report",
                    key="close_stock_report",
                ):
                    st.session_state.selected_symbol = None
                    st.rerun()

            metric_columns = st.columns(5)

            metric_columns[0].metric(
                "Grade",
                selected_stock.get("Grade", "—"),
            )

            metric_columns[1].metric(
                "Momo Score",
                selected_stock.get("Momo Score", "—"),
            )

            metric_columns[2].metric(
                "Dee Fit",
                selected_stock.get("Dee Fit", "—"),
            )

            metric_columns[3].metric(
                "Technical Score",
                selected_stock.get("Score", "—"),
            )

            metric_columns[4].metric(
                "Close",
                f"${selected_stock.get('Close', 0):.2f}",
            )

            st.subheader("Setup")
            st.write(
                selected_stock.get(
                    "Setup",
                    "Not classified",
                )
            )

            st.subheader("Current Scanner Read")
            st.write(
                selected_stock.get(
                    "Reasons",
                    "No reasons available.",
                )
            )

            detail_columns = st.columns(3)

            detail_columns[0].metric(
                "ATR %",
                selected_stock.get("ATR %", "—"),
            )

            detail_columns[1].metric(
                "RVOL",
                selected_stock.get("RVOL", "—"),
            )

            detail_columns[2].metric(
                "Distance From EMA21",
                (
                    f"{selected_stock.get('Distance EMA21 %', 0):.2f}%"
                ),
            )

            st.divider()
            st.subheader("Support and Resistance")

            support_col, resistance_col = st.columns(2)

            with support_col:
                st.markdown("#### Support")

                for label in [
                    "Support 1",
                    "Support 2",
                    "Support 3",
                ]:
                    value = selected_stock.get(label)

                    if valid_value(value):
                        st.metric(label, f"${float(value):.2f}")
                    else:
                        st.write(f"{label}: Not available")

            with resistance_col:
                st.markdown("#### Resistance")

                for label in [
                    "Resistance 1",
                    "Resistance 2",
                    "Resistance 3",
                ]:
                    value = selected_stock.get(label)

                    if valid_value(value):
                        upside = (
                            (
                                float(value)
                                - float(selected_stock["Close"])
                            )
                            / float(selected_stock["Close"])
                        ) * 100

                        st.metric(
                            label,
                            f"${float(value):.2f}",
                            f"{upside:.1f}% upside",
                        )
                    else:
                        st.write(f"{label}: Not available")

            st.divider()
            st.subheader("Structural Risk / Reward")

            rr_columns = st.columns(4)

            reference_entry = selected_stock.get(
                "Reference Entry"
            )
            risk_reference = selected_stock.get(
                "Risk Reference"
            )
            reward_reference = selected_stock.get(
                "Reward Reference"
            )
            risk_reward = selected_stock.get(
                "Risk Reward"
            )

            rr_columns[0].metric(
                "Reference Entry",
                (
                    f"${float(reference_entry):.2f}"
                    if valid_value(reference_entry)
                    else "—"
                ),
            )

            rr_columns[1].metric(
                "Risk Reference",
                (
                    f"${float(risk_reference):.2f}"
                    if valid_value(risk_reference)
                    else "—"
                ),
            )

            rr_columns[2].metric(
                "Reward Reference",
                (
                    f"${float(reward_reference):.2f}"
                    if valid_value(reward_reference)
                    else "—"
                ),
            )

            rr_columns[3].metric(
                "Risk / Reward",
                (
                    f"{float(risk_reward):.2f}R"
                    if valid_value(risk_reward)
                    else "—"
                ),
            )

            risk_detail_columns = st.columns(3)

            risk_per_share = selected_stock.get(
                "Risk Per Share"
            )
            reward_per_share = selected_stock.get(
                "Reward Per Share"
            )
            rr_status = selected_stock.get(
                "Risk Reward Status",
                "Not available",
            )

            risk_detail_columns[0].metric(
                "Risk Per Share",
                (
                    f"${float(risk_per_share):.2f}"
                    if valid_value(risk_per_share)
                    else "—"
                ),
            )

            risk_detail_columns[1].metric(
                "Reward Per Share",
                (
                    f"${float(reward_per_share):.2f}"
                    if valid_value(reward_per_share)
                    else "—"
                ),
            )

            risk_detail_columns[2].metric(
                "Structure Rating",
                rr_status,
            )

            st.caption(
                "This is a structural reference using the current "
                "close, nearest support, and nearest resistance. "
                "Final entry, stop, and T1–T3 calculations come next."
            )

            st.info(
                "Next roadmap item: T1, T2, and T3."
            )

    elif df is not None:
        st.warning(
            "The scan completed, but no qualifying stocks were found."
        )


with tabs[2]:
    st.header("AI Analysis")
    st.write("AI breakdowns will appear here.")


with tabs[3]:
    st.header("Watchlist")
    st.write("Saved stocks will appear here.")


with tabs[4]:
    st.header("Journal")
    st.write("Trade journal will appear here.")


with tabs[5]:
    st.header("Performance")
    st.write("Your stats will appear here.")


with tabs[6]:
    st.header("Settings")
    st.write("Strategy settings will appear here.")

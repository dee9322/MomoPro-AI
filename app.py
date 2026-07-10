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


# -----------------------------
# Session state
# -----------------------------
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


# -----------------------------
# Dashboard
# -----------------------------
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


# -----------------------------
# Scanner
# -----------------------------
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

        table_event = st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="scanner_table",
        )

        selected_rows = table_event.selection.rows

        if selected_rows:
            selected_index = selected_rows[0]
            selected_row = df.iloc[selected_index]
            st.session_state.selected_symbol = selected_row["Symbol"]

        selected_symbol = st.session_state.selected_symbol

        if selected_symbol:
            selected_stock = df[df["Symbol"] == selected_symbol].iloc[0]

            st.divider()

            header_left, header_right = st.columns([4, 1])

            with header_left:
                st.header(f"{selected_symbol} Stock Report")
                st.caption(
                    "This is the foundation for the full MomoPro AI report."
                )

            with header_right:
                if st.button("Close Report", key="close_stock_report"):
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
            st.write(selected_stock.get("Setup", "Not classified"))

            st.subheader("Current Scanner Read")
            st.write(selected_stock.get("Reasons", "No reasons available."))

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
                f"{selected_stock.get('Distance EMA21 %', 0):.2f}%",
            )

            st.info(
                "Next: this report will receive support, resistance, "
                "risk/reward, confidence, AI commentary, and T1–T3 targets."
            )

    elif df is not None:
        st.warning("The scan completed, but no qualifying stocks were found.")


# -----------------------------
# AI Analysis
# -----------------------------
with tabs[2]:
    st.header("AI Analysis")
    st.write("AI breakdowns will appear here.")


# -----------------------------
# Watchlist
# -----------------------------
with tabs[3]:
    st.header("Watchlist")
    st.write("Saved stocks will appear here.")


# -----------------------------
# Journal
# -----------------------------
with tabs[4]:
    st.header("Journal")
    st.write("Trade journal will appear here.")


# -----------------------------
# Performance
# -----------------------------
with tabs[5]:
    st.header("Performance")
    st.write("Your stats will appear here.")


# -----------------------------
# Settings
# -----------------------------
with tabs[6]:
    st.header("Settings")
    st.write("Strategy settings will appear here.")

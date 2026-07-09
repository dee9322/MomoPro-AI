import streamlit as st
from alpaca_test import test_alpaca_connection
from scanner import run_scan
st.set_page_config(
    page_title="MomoPro AI",
    page_icon="📈",
    layout="wide"
)

st.title("📈 MomoPro AI")
st.subheader("Your AI Swing Trading Partner")

tabs = st.tabs([
    "Dashboard",
    "Scanner",
    "AI Analysis",
    "Watchlist",
    "Journal",
    "Performance",
    "Settings"
])

with tabs[0]:
    st.header("Dashboard")

    if st.button("Test Alpaca Connection"):
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

    if st.button("Run Market Scan"):
        with st.spinner("Scanning market..."):
            df = run_scan()

        st.success(f"Scan complete! {len(df)} stocks analyzed.")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
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

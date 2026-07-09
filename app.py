import streamlit as st

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
    st.write("Market scan summary will appear here.")

with tabs[1]:
    st.header("Scanner")
    st.button("Run Market Scan")
    st.write("Top swing candidates will appear here.")

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

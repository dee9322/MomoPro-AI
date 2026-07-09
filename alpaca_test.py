import streamlit as st
from alpaca.trading.client import TradingClient

def test_alpaca_connection():
    try:
        api_key = st.secrets["ALPACA_API_KEY"]
        secret_key = st.secrets["ALPACA_SECRET_KEY"]

        client = TradingClient(api_key, secret_key, paper=True)
        account = client.get_account()

        return True, account.status, account.buying_power
    except Exception as e:
        return False, str(e), None

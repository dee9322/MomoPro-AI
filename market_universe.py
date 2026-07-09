import streamlit as st
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, AssetStatus


def get_market_universe(limit=500):
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_SECRET_KEY"]

    client = TradingClient(api_key, secret_key, paper=True)
    assets = client.get_all_assets()

    symbols = []

    for asset in assets:
        if (
            asset.asset_class == AssetClass.US_EQUITY
            and asset.status == AssetStatus.ACTIVE
            and asset.tradable
            and asset.symbol.isalpha()
        ):
            symbols.append(asset.symbol)

    symbols = sorted(list(set(symbols)))

    if limit and limit > 0:
        symbols = symbols[:limit]

    return symbols

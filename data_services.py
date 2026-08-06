"""Cached provider adapters used by the Streamlit entry point."""
from __future__ import annotations

import streamlit as st

from cache_policy import ttl_minutes
from comparison_research import research_comparison
from fda_intelligence import get_fda_enforcement
from news_intelligence import get_market_news, get_ticker_news
from relative_strength import get_relative_strength
from sec_intelligence import get_recent_filings
from smart_money import get_smart_money_intelligence
from trade_intelligence import get_trade_intelligence


def secret(name: str):
    try:
        return st.secrets.get(name)
    except Exception:
        return None


@st.cache_data(ttl=ttl_minutes("relative_strength", 60) * 60, show_spinner=False)
def load_relative_strength(symbol: str):
    return get_relative_strength(st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_SECRET_KEY"], symbol)


@st.cache_data(ttl=ttl_minutes("news", 15) * 60, show_spinner=False)
def load_market_news():
    return get_market_news(
        st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_SECRET_KEY"],
        alpha_vantage_api_key=secret("ALPHA_VANTAGE_API_KEY"),
        finnhub_api_key=secret("FINNHUB_API_KEY"), fmp_api_key=secret("FMP_API_KEY"),
    )


@st.cache_data(ttl=ttl_minutes("news", 15) * 60, show_spinner=False)
def load_ticker_news(symbol: str):
    return get_ticker_news(
        st.secrets["ALPACA_API_KEY"], st.secrets["ALPACA_SECRET_KEY"], symbol,
        alpha_vantage_api_key=secret("ALPHA_VANTAGE_API_KEY"),
        finnhub_api_key=secret("FINNHUB_API_KEY"), fmp_api_key=secret("FMP_API_KEY"),
    )


@st.cache_data(ttl=ttl_minutes("sec_filings", 60) * 60, show_spinner=False)
def load_sec_filings(symbol: str):
    return get_recent_filings(symbol)


@st.cache_data(ttl=3600, show_spinner=False)
def load_fda_records(company_name: str):
    return get_fda_enforcement(company_name)


@st.cache_data(ttl=ttl_minutes("smart_money", 30) * 60, show_spinner=False)
def load_smart_money(symbol: str):
    return get_smart_money_intelligence(
        symbol=symbol, alpaca_api_key=st.secrets["ALPACA_API_KEY"],
        alpaca_secret_key=st.secrets["ALPACA_SECRET_KEY"],
        alpha_vantage_api_key=secret("ALPHA_VANTAGE_API_KEY"),
        finnhub_api_key=secret("FINNHUB_API_KEY"), fmp_api_key=secret("FMP_API_KEY"),
    )


@st.cache_data(ttl=ttl_minutes("trade_intelligence", 30) * 60, show_spinner=False)
def load_trade_intelligence(symbol: str, stock_payload):
    return get_trade_intelligence(
        api_key=st.secrets["ALPACA_API_KEY"], secret_key=st.secrets["ALPACA_SECRET_KEY"],
        symbol=symbol, stock=stock_payload,
    )


@st.cache_data(ttl=1800, show_spinner=False)
def load_comparison_research(query: str):
    return research_comparison(
        query=query, alpaca_api_key=st.secrets["ALPACA_API_KEY"],
        alpaca_secret_key=st.secrets["ALPACA_SECRET_KEY"],
        alpha_vantage_api_key=secret("ALPHA_VANTAGE_API_KEY"),
        finnhub_api_key=secret("FINNHUB_API_KEY"), fmp_api_key=secret("FMP_API_KEY"),
    )

"""On-demand comparison research for MomoPro AI.

Researches a ticker/company that may not appear in the latest scanner results.
Uses connected provider evidence instead of unsupported model memory.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any

import pandas as pd
import requests

from news_intelligence import get_ticker_news, rank_news, summarize_news
from sec_intelligence import get_recent_filings


COMMON_COMPANIES = {
    "NIKE": "NKE",
    "APPLE": "AAPL",
    "MICROSOFT": "MSFT",
    "AMAZON": "AMZN",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    "META": "META",
    "FACEBOOK": "META",
    "TESLA": "TSLA",
    "NVIDIA": "NVDA",
    "AMD": "AMD",
    "ADVANCED MICRO DEVICES": "AMD",
    "PALANTIR": "PLTR",
    "SOFI": "SOFI",
}


def _clean_query(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def resolve_symbol(query: str, fmp_api_key: str | None = None) -> dict[str, Any]:
    clean = _clean_query(query)
    if not clean:
        return {"status": "Unavailable", "symbol": None, "name": None}

    upper = clean.upper()
    if upper in COMMON_COMPANIES:
        return {
            "status": "Available",
            "symbol": COMMON_COMPANIES[upper],
            "name": clean,
            "resolution": "common company mapping",
        }

    if re.fullmatch(r"[A-Za-z][A-Za-z.\-]{0,5}", clean):
        return {
            "status": "Available",
            "symbol": upper,
            "name": upper,
            "resolution": "ticker input",
        }

    if fmp_api_key:
        endpoints = [
            (
                "https://financialmodelingprep.com/stable/search-symbol",
                {"query": clean, "apikey": fmp_api_key},
            ),
            (
                "https://financialmodelingprep.com/api/v3/search",
                {"query": clean, "limit": 10, "apikey": fmp_api_key},
            ),
        ]
        for url, params in endpoints:
            try:
                response = requests.get(url, params=params, timeout=15)
                if response.status_code != 200:
                    continue
                payload = response.json()
                if isinstance(payload, dict):
                    payload = payload.get("data") or payload.get("results") or []
                if not isinstance(payload, list):
                    continue
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    symbol = item.get("symbol")
                    if not symbol:
                        continue
                    exchange = str(
                        item.get("exchangeShortName")
                        or item.get("exchange")
                        or item.get("stockExchange")
                        or ""
                    ).upper()
                    if exchange and not any(
                        marker in exchange
                        for marker in ("NASDAQ", "NYSE", "AMEX", "ARCA", "BATS", "US")
                    ):
                        continue
                    return {
                        "status": "Available",
                        "symbol": str(symbol).upper(),
                        "name": item.get("name") or item.get("companyName") or clean,
                        "resolution": "FMP company search",
                    }
            except Exception:
                continue

    return {
        "status": "Unavailable",
        "symbol": None,
        "name": clean,
        "resolution": "No matching US-listed ticker was found",
    }


def _fetch_daily_bars(
    symbol: str,
    alpaca_api_key: str,
    alpaca_secret_key: str,
    limit: int = 260,
) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=520)
    response = requests.get(
        f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
        headers={
            "APCA-API-KEY-ID": alpaca_api_key,
            "APCA-API-SECRET-KEY": alpaca_secret_key,
        },
        params={
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": limit,
            "adjustment": "all",
            "feed": "iex",
            "sort": "asc",
        },
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    bars = payload.get("bars", []) if isinstance(payload, dict) else []
    frame = pd.DataFrame(bars)
    if frame.empty:
        return frame
    return frame.rename(
        columns={
            "t": "timestamp",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
        }
    )


def _rsi(series: pd.Series, period: int = 14) -> float | None:
    if len(series) < period + 1:
        return None
    delta = series.diff()
    gains = delta.clip(lower=0).rolling(period).mean()
    losses = (-delta.clip(upper=0)).rolling(period).mean()
    last_loss = losses.iloc[-1]
    if pd.isna(last_loss):
        return None
    if float(last_loss) == 0:
        return 100.0
    rs = gains.iloc[-1] / last_loss
    return float(100 - (100 / (1 + rs)))


def _technical_snapshot(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty or "close" not in frame:
        return {"status": "Unavailable"}

    close = pd.to_numeric(frame["close"], errors="coerce").dropna()
    volume = pd.to_numeric(frame.get("volume"), errors="coerce").dropna()
    if close.empty:
        return {"status": "Unavailable"}

    latest = float(close.iloc[-1])
    ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1]) if len(close) >= 21 else None
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1]) if len(close) >= 50 else None
    ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1]) if len(close) >= 200 else None

    def pct_return(days: int) -> float | None:
        if len(close) <= days:
            return None
        base = float(close.iloc[-days - 1])
        return ((latest / base) - 1) * 100 if base else None

    trend_parts = []
    if ema21 is not None:
        trend_parts.append(latest > ema21)
    if ema50 is not None:
        trend_parts.append(latest > ema50)
    if ema200 is not None:
        trend_parts.append(latest > ema200)

    if trend_parts and all(trend_parts):
        trend = "Bullish"
    elif trend_parts and not any(trend_parts):
        trend = "Bearish"
    else:
        trend = "Mixed"

    avg_volume20 = float(volume.tail(20).mean()) if not volume.empty else None
    latest_volume = float(volume.iloc[-1]) if not volume.empty else None
    rvol = (
        latest_volume / avg_volume20
        if latest_volume is not None and avg_volume20 not in (None, 0)
        else None
    )

    return {
        "status": "Available",
        "close": latest,
        "ema21": ema21,
        "ema50": ema50,
        "ema200": ema200,
        "distance_from_ema21_pct": ((latest / ema21) - 1) * 100 if ema21 else None,
        "rsi14": _rsi(close),
        "return_5d_pct": pct_return(5),
        "return_20d_pct": pct_return(20),
        "return_60d_pct": pct_return(60),
        "latest_volume": latest_volume,
        "average_volume_20d": avg_volume20,
        "rvol": rvol,
        "trend": trend,
    }


def research_comparison(
    query: str,
    alpaca_api_key: str,
    alpaca_secret_key: str,
    alpha_vantage_api_key: str | None = None,
    finnhub_api_key: str | None = None,
    fmp_api_key: str | None = None,
) -> dict[str, Any]:
    resolved = resolve_symbol(query, fmp_api_key=fmp_api_key)
    symbol = resolved.get("symbol")
    if not symbol:
        return {"status": "Unavailable", "query": query, "resolution": resolved}

    try:
        technical = _technical_snapshot(
            _fetch_daily_bars(symbol, alpaca_api_key, alpaca_secret_key)
        )
    except Exception as exc:
        technical = {"status": "Unavailable", "reason": str(exc)}

    try:
        news_items = get_ticker_news(
            alpaca_api_key,
            alpaca_secret_key,
            symbol,
            alpha_vantage_api_key=alpha_vantage_api_key,
            finnhub_api_key=finnhub_api_key,
            fmp_api_key=fmp_api_key,
        )
        ranked_news = rank_news(news_items)
        news = {
            "summary": summarize_news(ranked_news),
            "articles": ranked_news[:10],
        }
    except Exception as exc:
        news = {"summary": {"status": "Unavailable", "reason": str(exc)}, "articles": []}

    try:
        sec_package = get_recent_filings(symbol)
        filings = sec_package.get("filings", []) if isinstance(sec_package, dict) else []
    except Exception:
        filings = []

    return {
        "status": "Available",
        "query": query,
        "symbol": symbol,
        "company_name": resolved.get("name"),
        "resolution": resolved,
        "technical": technical,
        "news": news,
        "sec_filings": filings[:8],
        "research_scope": (
            "On-demand provider research using Alpaca market data, "
            "multi-source news, and SEC records."
        ),
    }


def detect_comparison_query(question: str, current_symbol: str) -> str | None:
    text = _clean_query(question)
    if not text:
        return None

    patterns = [
        r"\bbetter (?:entry|trade|setup|stock)?\s*than\s+([A-Za-z][A-Za-z0-9 .&'\-]{1,35})",
        r"\bcompare\s+(?:this|it|%s)\s+(?:with|to|against)\s+([A-Za-z][A-Za-z0-9 .&'\-]{1,35})"
        % re.escape(current_symbol),
        r"\bversus\s+([A-Za-z][A-Za-z0-9 .&'\-]{1,35})",
        r"\bvs\.?\s+([A-Za-z][A-Za-z0-9 .&'\-]{1,35})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1)
        candidate = re.split(
            r"[?.,;:]|\b(?:right now|today|currently|for a swing)\b",
            candidate,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
        if candidate and candidate.upper() != current_symbol.upper():
            return candidate
    return None

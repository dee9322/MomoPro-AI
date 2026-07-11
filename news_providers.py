from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests


DEFAULT_TIMEOUT = 12
USER_AGENT = "MomoProAI/0.3 news-intelligence"


def _get_json(url: str, params: dict[str, Any]) -> Any:
    response = requests.get(
        url,
        params=params,
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, dict):
        error_text = (
            payload.get("Error Message")
            or payload.get("Information")
            or payload.get("Note")
            or payload.get("error")
        )
        if error_text:
            raise RuntimeError(str(error_text))

    return payload


def fetch_alpha_vantage_news(
    api_key: str | None,
    symbol: str | None = None,
    lookback_days: int = 14,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if not api_key:
        return []

    start = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    params: dict[str, Any] = {
        "function": "NEWS_SENTIMENT",
        "apikey": api_key,
        "time_from": start.strftime("%Y%m%dT%H%M"),
        "sort": "LATEST",
        "limit": min(max(limit, 1), 1000),
    }
    if symbol:
        params["tickers"] = symbol.upper()
    else:
        params["topics"] = "financial_markets"

    payload = _get_json("https://www.alphavantage.co/query", params)
    feed = payload.get("feed", []) if isinstance(payload, dict) else []
    results: list[dict[str, Any]] = []

    for item in feed:
        ticker_sentiment = item.get("ticker_sentiment") or []
        symbols = [
            str(entry.get("ticker", "")).upper()
            for entry in ticker_sentiment
            if entry.get("ticker")
        ]
        results.append(
            {
                "provider": "Alpha Vantage",
                "provider_id": item.get("url"),
                "headline": item.get("title"),
                "summary": item.get("summary"),
                "symbols": symbols,
                "created_at": item.get("time_published"),
                "updated_at": None,
                "url": item.get("url"),
                "source": item.get("source") or "Alpha Vantage",
                "provider_sentiment": item.get("overall_sentiment_label"),
                "provider_sentiment_score": item.get("overall_sentiment_score"),
                "is_press_release": False,
            }
        )

    return results


def fetch_finnhub_company_news(
    api_key: str | None,
    symbol: str,
    lookback_days: int = 14,
) -> list[dict[str, Any]]:
    if not api_key or not symbol:
        return []

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=lookback_days)
    payload = _get_json(
        "https://finnhub.io/api/v1/company-news",
        {
            "symbol": symbol.upper(),
            "from": start.isoformat(),
            "to": end.isoformat(),
            "token": api_key,
        },
    )

    results: list[dict[str, Any]] = []
    for item in payload if isinstance(payload, list) else []:
        timestamp = item.get("datetime")
        created_at = (
            datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
            if isinstance(timestamp, (int, float))
            else timestamp
        )
        related = str(item.get("related") or "")
        symbols = [part.strip().upper() for part in related.split(",") if part.strip()]
        if symbol.upper() not in symbols:
            symbols.append(symbol.upper())

        results.append(
            {
                "provider": "Finnhub",
                "provider_id": item.get("id"),
                "headline": item.get("headline"),
                "summary": item.get("summary"),
                "symbols": symbols,
                "created_at": created_at,
                "updated_at": None,
                "url": item.get("url"),
                "source": item.get("source") or "Finnhub",
                "provider_sentiment": None,
                "provider_sentiment_score": None,
                "is_press_release": item.get("category") == "company",
            }
        )

    return results


def fetch_finnhub_market_news(
    api_key: str | None,
    limit: int = 60,
) -> list[dict[str, Any]]:
    if not api_key:
        return []

    payload = _get_json(
        "https://finnhub.io/api/v1/news",
        {"category": "general", "minId": 0, "token": api_key},
    )

    results: list[dict[str, Any]] = []
    for item in (payload if isinstance(payload, list) else [])[:limit]:
        timestamp = item.get("datetime")
        created_at = (
            datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
            if isinstance(timestamp, (int, float))
            else timestamp
        )
        related = str(item.get("related") or "")
        symbols = [part.strip().upper() for part in related.split(",") if part.strip()]
        results.append(
            {
                "provider": "Finnhub",
                "provider_id": item.get("id"),
                "headline": item.get("headline"),
                "summary": item.get("summary"),
                "symbols": symbols,
                "created_at": created_at,
                "updated_at": None,
                "url": item.get("url"),
                "source": item.get("source") or "Finnhub",
                "provider_sentiment": None,
                "provider_sentiment_score": None,
                "is_press_release": False,
            }
        )

    return results


def _normalize_fmp_item(
    item: dict[str, Any],
    provider_label: str,
    fallback_symbol: str | None = None,
    is_press_release: bool = False,
) -> dict[str, Any]:
    symbol_value = item.get("symbol") or item.get("symbols") or fallback_symbol
    if isinstance(symbol_value, str):
        symbols = [part.strip().upper() for part in symbol_value.split(",") if part.strip()]
    elif isinstance(symbol_value, list):
        symbols = [str(part).upper() for part in symbol_value]
    else:
        symbols = []

    return {
        "provider": provider_label,
        "provider_id": item.get("url") or item.get("id"),
        "headline": item.get("title") or item.get("headline"),
        "summary": item.get("text") or item.get("content") or item.get("snippet") or item.get("summary"),
        "symbols": symbols,
        "created_at": item.get("publishedDate") or item.get("date") or item.get("publishedAt"),
        "updated_at": None,
        "url": item.get("url") or item.get("link"),
        "source": item.get("site") or item.get("publisher") or provider_label,
        "provider_sentiment": None,
        "provider_sentiment_score": None,
        "is_press_release": is_press_release,
    }


def fetch_fmp_market_news(
    api_key: str | None,
    limit: int = 60,
) -> list[dict[str, Any]]:
    if not api_key:
        return []

    results: list[dict[str, Any]] = []
    endpoints = [
        ("https://financialmodelingprep.com/stable/news/stock-latest", "FMP Stock News"),
        ("https://financialmodelingprep.com/stable/news/general-latest", "FMP General News"),
    ]

    for url, label in endpoints:
        try:
            payload = _get_json(
                url,
                {"page": 0, "limit": min(limit, 100), "apikey": api_key},
            )
            for item in payload if isinstance(payload, list) else []:
                results.append(_normalize_fmp_item(item, label))
        except Exception:
            continue

    return results


def fetch_fmp_ticker_news(
    api_key: str | None,
    symbol: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if not api_key or not symbol:
        return []

    clean_symbol = symbol.upper()
    results: list[dict[str, Any]] = []
    endpoints = [
        (
            "https://financialmodelingprep.com/stable/news/stock",
            {"symbols": clean_symbol, "page": 0, "limit": limit, "apikey": api_key},
            "FMP Stock News",
            False,
        ),
        (
            "https://financialmodelingprep.com/stable/news/press-releases",
            {"symbols": clean_symbol, "page": 0, "limit": limit, "apikey": api_key},
            "FMP Press Release",
            True,
        ),
    ]

    for url, params, label, is_press_release in endpoints:
        try:
            payload = _get_json(url, params)
            for item in payload if isinstance(payload, list) else []:
                results.append(
                    _normalize_fmp_item(
                        item,
                        label,
                        fallback_symbol=clean_symbol,
                        is_press_release=is_press_release,
                    )
                )
        except Exception:
            continue

    return results

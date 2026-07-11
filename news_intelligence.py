from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from alpaca.data.historical import NewsClient
from alpaca.data.requests import NewsRequest

from news_providers import (
    fetch_alpha_vantage_news,
    fetch_finnhub_company_news,
    fetch_finnhub_market_news,
    fetch_fmp_market_news,
    fetch_fmp_ticker_news,
)


POSITIVE_WORDS = {
    "beat", "beats", "surge", "surges", "record", "approval", "approved",
    "upgrade", "upgraded", "raises", "raised", "growth", "profit", "profits",
    "partnership", "contract", "buyback", "dividend", "breakthrough", "wins",
    "strong", "bullish", "outperform", "launch", "expands", "acquisition",
}
NEGATIVE_WORDS = {
    "miss", "misses", "cut", "cuts", "downgrade", "downgraded", "lawsuit",
    "investigation", "recall", "warning", "loss", "losses", "fraud", "delay",
    "reject", "rejected", "offering", "dilution", "bankruptcy", "weak", "bearish",
    "plunge", "falls", "slump", "resigns", "restatement", "probe", "halt",
}
HIGH_IMPACT_WORDS = {
    "earnings", "guidance", "sec", "8-k", "10-k", "10-q", "fda", "approval",
    "trial", "merger", "acquisition", "offering", "bankruptcy", "recall",
    "upgrade", "downgrade", "investigation", "forecast", "contract",
}
SOURCE_PRIORITY = {
    "FMP Press Release": 6,
    "Alpaca/Benzinga": 5,
    "Alpha Vantage": 4,
    "Finnhub": 3,
    "FMP Stock News": 3,
    "FMP General News": 2,
}


def _article_value(article: Any, key: str, default: Any = None) -> Any:
    if isinstance(article, dict):
        return article.get(key, default)
    return getattr(article, key, default)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _parse_datetime(value: Any) -> str | None:
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        formats = [
            "%Y%m%dT%H%M%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        dt = None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            for fmt in formats:
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
        if dt is None:
            return text

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def classify_sentiment(text: str) -> tuple[str, int]:
    lowered = (text or "").lower()
    positive = sum(1 for word in POSITIVE_WORDS if word in lowered)
    negative = sum(1 for word in NEGATIVE_WORDS if word in lowered)

    if positive >= negative + 2:
        return "Bullish", min(95, 55 + positive * 8)
    if negative >= positive + 2:
        return "Bearish", min(95, 55 + negative * 8)
    if positive and negative:
        return "Mixed", 55
    if positive > negative:
        return "Bullish", 60
    if negative > positive:
        return "Bearish", 60
    return "Neutral", 50


def _provider_sentiment(label: Any, score: Any) -> tuple[str, int] | None:
    text = str(label or "").lower()
    if not text:
        return None

    try:
        numeric_score = float(score)
        confidence = max(50, min(95, int(50 + abs(numeric_score) * 45)))
    except (TypeError, ValueError):
        confidence = 60

    if "bullish" in text:
        return "Bullish", confidence
    if "bearish" in text:
        return "Bearish", confidence
    if "neutral" in text:
        return "Neutral", confidence
    return None


def classify_category(text: str, is_press_release: bool = False) -> str:
    if is_press_release:
        return "Company Press Release"

    lowered = (text or "").lower()
    if any(term in lowered for term in ("earnings", "eps", "revenue", "guidance")):
        return "Earnings"
    if any(term in lowered for term in ("upgrade", "downgrade", "price target", "analyst")):
        return "Analyst Action"
    if any(term in lowered for term in ("fda", "clinical trial", "phase 1", "phase 2", "phase 3")):
        return "FDA / Clinical"
    if any(term in lowered for term in ("8-k", "10-k", "10-q", "sec filing", "form 4")):
        return "SEC / Filing"
    if any(term in lowered for term in ("merger", "acquisition", "buyout")):
        return "M&A"
    if any(term in lowered for term in ("offering", "dilution", "secondary offering")):
        return "Capital Raise"
    if any(term in lowered for term in ("fed", "inflation", "cpi", "jobs report", "rates")):
        return "Macro"
    return "General"


def classify_impact(text: str, symbols: list[str], is_press_release: bool = False) -> str:
    lowered = (text or "").lower()
    hits = sum(1 for word in HIGH_IMPACT_WORDS if word in lowered)
    if hits >= 2:
        return "High"
    if hits == 1 or is_press_release or len(symbols) <= 2:
        return "Medium"
    return "Low"


def _normalize_article(article: Any, default_provider: str = "Alpaca/Benzinga") -> dict[str, Any]:
    headline = _clean_text(_article_value(article, "headline") or _article_value(article, "title"))
    summary = _clean_text(_article_value(article, "summary") or _article_value(article, "text"))
    raw_symbols = _article_value(article, "symbols", []) or []
    if isinstance(raw_symbols, str):
        symbols = [part.strip().upper() for part in raw_symbols.split(",") if part.strip()]
    else:
        symbols = [str(part).upper() for part in raw_symbols if part]

    created_at = _parse_datetime(_article_value(article, "created_at"))
    updated_at = _parse_datetime(_article_value(article, "updated_at"))
    url = _clean_text(_article_value(article, "url")) or None
    source = _clean_text(_article_value(article, "source")) or default_provider
    provider = _clean_text(_article_value(article, "provider")) or default_provider
    article_id = _article_value(article, "provider_id", _article_value(article, "id"))
    is_press_release = bool(_article_value(article, "is_press_release", False))

    combined = f"{headline} {summary}"
    provider_sentiment = _provider_sentiment(
        _article_value(article, "provider_sentiment"),
        _article_value(article, "provider_sentiment_score"),
    )
    sentiment, sentiment_score = provider_sentiment or classify_sentiment(combined)
    category = classify_category(combined, is_press_release=is_press_release)
    impact = classify_impact(combined, symbols, is_press_release=is_press_release)

    why_it_matters = summary
    if not why_it_matters:
        why_it_matters = f"{impact}-impact {category.lower()} headline with {sentiment.lower()} sentiment."
    elif len(why_it_matters) > 320:
        why_it_matters = why_it_matters[:317].rstrip() + "..."

    return {
        "id": article_id,
        "headline": headline,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "symbols": sorted(set(symbols)),
        "created_at": created_at,
        "updated_at": updated_at,
        "url": url,
        "source": source,
        "provider": provider,
        "sentiment": sentiment,
        "sentiment_score": sentiment_score,
        "impact": impact,
        "category": category,
        "is_press_release": is_press_release,
    }


def _canonical_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))
    except Exception:
        return url.lower().strip()


def _headline_key(headline: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", headline.lower()).strip()


def _is_duplicate(candidate: dict[str, Any], kept: list[dict[str, Any]]) -> bool:
    candidate_url = _canonical_url(candidate.get("url"))
    candidate_title = _headline_key(candidate.get("headline", ""))

    for existing in kept:
        existing_url = _canonical_url(existing.get("url"))
        if candidate_url and existing_url and candidate_url == existing_url:
            return True

        existing_title = _headline_key(existing.get("headline", ""))
        if not candidate_title or not existing_title:
            continue
        if candidate_title == existing_title:
            return True
        if SequenceMatcher(None, candidate_title, existing_title).ratio() >= 0.92:
            return True

    return False


def _deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        items,
        key=lambda item: (
            SOURCE_PRIORITY.get(item.get("provider", ""), 1),
            str(item.get("created_at") or ""),
        ),
        reverse=True,
    )
    kept: list[dict[str, Any]] = []
    for item in ordered:
        if not item.get("headline"):
            continue
        if not _is_duplicate(item, kept):
            kept.append(item)
    return kept


def _fetch_alpaca_news(
    api_key: str,
    secret_key: str,
    symbols: str | None,
    lookback_days: int,
    limit: int,
) -> list[dict[str, Any]]:
    client = NewsClient(api_key, secret_key)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    request = NewsRequest(
        start=start,
        end=end,
        sort="desc",
        symbols=symbols,
        limit=limit,
        include_content=False,
        exclude_contentless=False,
    )
    response = client.get_news(request)
    response_data = getattr(response, "data", None)

    if isinstance(response_data, dict):
        news_items = response_data.get("news", [])
    elif isinstance(response, dict):
        news_items = response.get("news", [])
    else:
        news_items = []

    return [_normalize_article(article, "Alpaca/Benzinga") for article in news_items or []]


def _safe_fetch(fetcher, *args, **kwargs) -> list[dict[str, Any]]:
    try:
        raw_items = fetcher(*args, **kwargs)
        return [_normalize_article(item, item.get("provider", "Unknown")) for item in raw_items]
    except Exception:
        return []


def get_market_news(
    api_key: str,
    secret_key: str,
    alpha_vantage_api_key: str | None = None,
    finnhub_api_key: str | None = None,
    fmp_api_key: str | None = None,
    lookback_days: int = 3,
    limit: int = 60,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    items.extend(_safe_fetch(_fetch_alpaca_news, api_key, secret_key, None, lookback_days, limit))
    items.extend(_safe_fetch(fetch_finnhub_market_news, finnhub_api_key, limit))
    items.extend(_safe_fetch(fetch_fmp_market_news, fmp_api_key, limit))

    # Alpha Vantage's free tier is very limited, so reserve it for market refreshes
    # and explicit ticker requests only—not every scanned symbol.
    items.extend(
        _safe_fetch(
            fetch_alpha_vantage_news,
            alpha_vantage_api_key,
            None,
            lookback_days,
            min(limit, 50),
        )
    )
    return _deduplicate(items)


def get_ticker_news(
    api_key: str,
    secret_key: str,
    symbol: str,
    alpha_vantage_api_key: str | None = None,
    finnhub_api_key: str | None = None,
    fmp_api_key: str | None = None,
    lookback_days: int = 14,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clean_symbol = symbol.strip().upper()
    if not clean_symbol:
        return []

    items: list[dict[str, Any]] = []
    items.extend(_safe_fetch(_fetch_alpaca_news, api_key, secret_key, clean_symbol, lookback_days, limit))
    items.extend(_safe_fetch(fetch_finnhub_company_news, finnhub_api_key, clean_symbol, lookback_days))
    items.extend(_safe_fetch(fetch_fmp_ticker_news, fmp_api_key, clean_symbol, limit))
    items.extend(
        _safe_fetch(
            fetch_alpha_vantage_news,
            alpha_vantage_api_key,
            clean_symbol,
            lookback_days,
            min(limit, 50),
        )
    )
    return _deduplicate(items)


def summarize_news(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {
            "status": "Unavailable",
            "bullish": 0,
            "bearish": 0,
            "mixed": 0,
            "neutral": 0,
            "high_impact": 0,
            "overall_sentiment": "No recent news",
            "source_counts": {},
        }

    counts = {"Bullish": 0, "Bearish": 0, "Mixed": 0, "Neutral": 0}
    source_counts: dict[str, int] = {}
    for item in items:
        sentiment = item.get("sentiment", "Neutral")
        counts[sentiment] = counts.get(sentiment, 0) + 1
        provider = item.get("provider") or item.get("source") or "Unknown"
        source_counts[provider] = source_counts.get(provider, 0) + 1

    bullish = counts["Bullish"]
    bearish = counts["Bearish"]
    if bullish >= bearish + 2:
        overall = "Bullish"
    elif bearish >= bullish + 2:
        overall = "Bearish"
    elif bullish or bearish:
        overall = "Mixed"
    else:
        overall = "Neutral"

    return {
        "status": "Available",
        "bullish": bullish,
        "bearish": bearish,
        "mixed": counts["Mixed"],
        "neutral": counts["Neutral"],
        "high_impact": sum(1 for item in items if item.get("impact") == "High"),
        "overall_sentiment": overall,
        "source_counts": source_counts,
    }


def rank_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    impact_rank = {"High": 3, "Medium": 2, "Low": 1}
    sentiment_rank = {"Bearish": 4, "Bullish": 3, "Mixed": 2, "Neutral": 1}
    return sorted(
        items,
        key=lambda item: (
            impact_rank.get(item.get("impact"), 0),
            SOURCE_PRIORITY.get(item.get("provider", ""), 1),
            sentiment_rank.get(item.get("sentiment"), 0),
            str(item.get("created_at") or ""),
        ),
        reverse=True,
    )

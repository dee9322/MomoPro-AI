from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from alpaca.data.historical import NewsClient
from alpaca.data.requests import NewsRequest


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
    "upgrade", "downgrade", "investigation", "guidance", "forecast", "contract",
}


def _article_value(article: Any, key: str, default: Any = None) -> Any:
    if isinstance(article, dict):
        return article.get(key, default)
    return getattr(article, key, default)


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


def classify_category(text: str) -> str:
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


def classify_impact(text: str, symbols: list[str]) -> str:
    lowered = (text or "").lower()
    hits = sum(1 for word in HIGH_IMPACT_WORDS if word in lowered)
    if hits >= 2:
        return "High"
    if hits == 1 or len(symbols) <= 2:
        return "Medium"
    return "Low"


def _normalize_article(article: Any) -> dict[str, Any]:
    headline = str(_article_value(article, "headline", "Untitled"))
    summary = str(_article_value(article, "summary", "") or "")
    symbols = list(_article_value(article, "symbols", []) or [])
    created_at = _article_value(article, "created_at")
    updated_at = _article_value(article, "updated_at")
    url = _article_value(article, "url")
    source = _article_value(article, "source", "Alpaca/Benzinga")
    article_id = _article_value(article, "id")

    combined = f"{headline} {summary}"
    sentiment, sentiment_score = classify_sentiment(combined)
    category = classify_category(combined)
    impact = classify_impact(combined, symbols)

    why_it_matters = summary.strip()
    if not why_it_matters:
        why_it_matters = (
            f"{impact}-impact {category.lower()} headline with {sentiment.lower()} sentiment."
        )
    elif len(why_it_matters) > 260:
        why_it_matters = why_it_matters[:257].rstrip() + "..."

    return {
        "id": article_id,
        "headline": headline,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "symbols": symbols,
        "created_at": created_at,
        "updated_at": updated_at,
        "url": url,
        "source": source,
        "sentiment": sentiment,
        "sentiment_score": sentiment_score,
        "impact": impact,
        "category": category,
    }


def _fetch_news(
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

    # Alpaca-py returns a NewsSet. Its articles live in
    # response.data["news"], not response.news. Iterating the NewsSet
    # itself yields its model fields (data and next_page_token), which
    # caused the two fake "Untitled" placeholder rows.
    response_data = getattr(response, "data", None)

    if isinstance(response_data, dict):
        news_items = response_data.get("news", [])
    elif isinstance(response, dict):
        news_items = response.get("news", [])
    else:
        news_items = []

    normalized = []
    for article in news_items or []:
        item = _normalize_article(article)

        # Never display synthetic placeholder articles when the API
        # did not supply a real headline.
        if item["headline"].strip() and item["headline"] != "Untitled":
            normalized.append(item)

    return normalized


def get_market_news(
    api_key: str,
    secret_key: str,
    lookback_days: int = 3,
    limit: int = 60,
) -> list[dict[str, Any]]:
    return _fetch_news(api_key, secret_key, None, lookback_days, limit)


def get_ticker_news(
    api_key: str,
    secret_key: str,
    symbol: str,
    lookback_days: int = 14,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clean_symbol = symbol.strip().upper()
    if not clean_symbol:
        return []
    return _fetch_news(api_key, secret_key, clean_symbol, lookback_days, limit)


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
        }

    counts = {"Bullish": 0, "Bearish": 0, "Mixed": 0, "Neutral": 0}
    for item in items:
        counts[item.get("sentiment", "Neutral")] = counts.get(item.get("sentiment", "Neutral"), 0) + 1

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
    }


def rank_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    impact_rank = {"High": 3, "Medium": 2, "Low": 1}
    sentiment_rank = {"Bearish": 4, "Bullish": 3, "Mixed": 2, "Neutral": 1}
    return sorted(
        items,
        key=lambda item: (
            impact_rank.get(item.get("impact"), 0),
            sentiment_rank.get(item.get("sentiment"), 0),
            str(item.get("created_at") or ""),
        ),
        reverse=True,
    )

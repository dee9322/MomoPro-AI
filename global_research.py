"""Independent broad-market research support for Global Ask Momo AI."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

import requests

from comparison_research import research_comparison, resolve_symbol
from news_intelligence import get_market_news, rank_news, summarize_news


def _safe_json(url: str, params: dict[str, Any], timeout: int = 18) -> Any:
    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _normalize_mover(item: dict[str, Any], source: str, bucket: str) -> dict[str, Any] | None:
    symbol = (
        item.get("ticker")
        or item.get("symbol")
        or item.get("Symbol")
        or item.get("code")
    )
    if not symbol:
        return None

    def value(*keys):
        for key in keys:
            if key in item and item.get(key) not in (None, ""):
                return item.get(key)
        return None

    return {
        "symbol": str(symbol).upper(),
        "name": value("name", "companyName", "company_name"),
        "price": value("price", "last", "lastPrice"),
        "change": value("change_amount", "change", "changes"),
        "change_percent": value("change_percentage", "changesPercentage", "changePercent"),
        "volume": value("volume", "Volume"),
        "source": source,
        "bucket": bucket,
    }


def _dedupe_candidates(items: list[dict[str, Any]], limit: int = 60) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        symbol = str(item.get("symbol") or "").upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        output.append(item)
        if len(output) >= limit:
            break
    return output


def _alpha_vantage_discovery(api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return {"status": "Unavailable", "reason": "No Alpha Vantage key"}

    try:
        payload = _safe_json(
            "https://www.alphavantage.co/query",
            {"function": "TOP_GAINERS_LOSERS", "apikey": api_key},
        )
    except Exception as exc:
        return {"status": "Unavailable", "reason": str(exc)}

    if not isinstance(payload, dict):
        return {"status": "Unavailable", "reason": "Unexpected response"}

    if payload.get("Information") or payload.get("Note"):
        return {
            "status": "Unavailable",
            "reason": payload.get("Information") or payload.get("Note"),
        }

    candidates: list[dict[str, Any]] = []
    mapping = [
        ("top_gainers", "Top Gainers"),
        ("top_losers", "Top Losers"),
        ("most_actively_traded", "Most Active"),
    ]
    for key, bucket in mapping:
        for item in payload.get(key, []) or []:
            normalized = _normalize_mover(item, "Alpha Vantage", bucket)
            if normalized:
                candidates.append(normalized)

    return {
        "status": "Available",
        "last_updated": payload.get("last_updated"),
        "candidates": candidates,
    }


def _fmp_discovery(api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return {"status": "Unavailable", "reason": "No FMP key"}

    endpoint_groups = [
        (
            "Top Gainers",
            [
                "https://financialmodelingprep.com/stable/biggest-gainers",
                "https://financialmodelingprep.com/api/v3/stock_market/gainers",
            ],
        ),
        (
            "Most Active",
            [
                "https://financialmodelingprep.com/stable/most-actives",
                "https://financialmodelingprep.com/api/v3/stock_market/actives",
            ],
        ),
        (
            "Top Losers",
            [
                "https://financialmodelingprep.com/stable/biggest-losers",
                "https://financialmodelingprep.com/api/v3/stock_market/losers",
            ],
        ),
    ]

    candidates: list[dict[str, Any]] = []
    errors: list[str] = []

    for bucket, urls in endpoint_groups:
        payload = None
        for url in urls:
            try:
                payload = _safe_json(url, {"apikey": api_key})
                if isinstance(payload, dict):
                    payload = payload.get("data") or payload.get("results") or payload.get("items")
                if isinstance(payload, list):
                    break
            except Exception as exc:
                errors.append(f"{bucket}: {exc}")
                payload = None

        if not isinstance(payload, list):
            continue

        for item in payload[:30]:
            if not isinstance(item, dict):
                continue
            normalized = _normalize_mover(item, "FMP", bucket)
            if normalized:
                candidates.append(normalized)

    if not candidates:
        return {
            "status": "Unavailable",
            "reason": "; ".join(errors[-3:]) or "No FMP discovery data",
        }

    return {"status": "Available", "candidates": candidates}


def discover_broad_market_candidates(
    alpha_vantage_api_key: str | None = None,
    fmp_api_key: str | None = None,
) -> dict[str, Any]:
    """Build an independent candidate pool outside the MomoPro scan.

    This is a broad market discovery pass, not a literal exhaustive scan of
    every listed security.
    """
    av = _alpha_vantage_discovery(alpha_vantage_api_key)
    fmp = _fmp_discovery(fmp_api_key)

    combined: list[dict[str, Any]] = []
    combined.extend(av.get("candidates", []) if isinstance(av, dict) else [])
    combined.extend(fmp.get("candidates", []) if isinstance(fmp, dict) else [])

    return {
        "status": "Available" if combined else "Unavailable",
        "scope": (
            "Independent broad-market discovery using external top-gainer, "
            "most-active, and top-loser feeds. This is not a literal scan of "
            "every listed security."
        ),
        "providers": {
            "alpha_vantage": av.get("status") if isinstance(av, dict) else "Unavailable",
            "fmp": fmp.get("status") if isinstance(fmp, dict) else "Unavailable",
        },
        "candidates": _dedupe_candidates(combined, limit=60),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _explicit_ticker_tokens(question: str) -> list[str]:
    tokens = re.findall(r"\b[A-Z]{1,5}(?:\.[A-Z])?\b", question or "")
    blocked = {
        "AI", "EMA", "RSI", "MACD", "ATR", "SEC", "FDA", "ETF", "IPO",
        "USD", "CEO", "CFO", "IV", "R", "THE", "AND", "OR", "VS",
    }
    result: list[str] = []
    for token in tokens:
        if token in blocked or token in result:
            continue
        result.append(token)
    return result[:5]


def _named_company_candidates(question: str) -> list[str]:
    common = {
        "nike": "Nike",
        "apple": "Apple",
        "microsoft": "Microsoft",
        "amazon": "Amazon",
        "google": "Google",
        "alphabet": "Alphabet",
        "meta": "Meta",
        "facebook": "Meta",
        "tesla": "Tesla",
        "nvidia": "Nvidia",
        "palantir": "Palantir",
        "sofi": "SoFi",
    }
    lower = (question or "").lower()
    return [display for key, display in common.items() if key in lower][:5]


def research_explicit_entities(
    question: str,
    alpaca_api_key: str,
    alpaca_secret_key: str,
    alpha_vantage_api_key: str | None = None,
    finnhub_api_key: str | None = None,
    fmp_api_key: str | None = None,
) -> list[dict[str, Any]]:
    queries = _explicit_ticker_tokens(question) + _named_company_candidates(question)
    output: list[dict[str, Any]] = []
    seen: set[str] = set()

    for query in queries:
        try:
            resolved = resolve_symbol(query, fmp_api_key=fmp_api_key)
            symbol = str(resolved.get("symbol") or "").upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            output.append(
                research_comparison(
                    query=query,
                    alpaca_api_key=alpaca_api_key,
                    alpaca_secret_key=alpaca_secret_key,
                    alpha_vantage_api_key=alpha_vantage_api_key,
                    finnhub_api_key=finnhub_api_key,
                    fmp_api_key=fmp_api_key,
                )
            )
        except Exception:
            continue

    return output[:5]


def build_global_research_context(
    question: str,
    alpaca_api_key: str,
    alpaca_secret_key: str,
    alpha_vantage_api_key: str | None = None,
    finnhub_api_key: str | None = None,
    fmp_api_key: str | None = None,
    momo_scan_reference: list[dict[str, Any]] | None = None,
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    discovery = discover_broad_market_candidates(
        alpha_vantage_api_key=alpha_vantage_api_key,
        fmp_api_key=fmp_api_key,
    )

    try:
        market_articles = get_market_news(
            alpaca_api_key,
            alpaca_secret_key,
            alpha_vantage_api_key=alpha_vantage_api_key,
            finnhub_api_key=finnhub_api_key,
            fmp_api_key=fmp_api_key,
        )
        ranked_news = rank_news(market_articles)
        market_news = {
            "summary": summarize_news(ranked_news),
            "articles": ranked_news[:20],
        }
    except Exception as exc:
        market_news = {
            "summary": {"status": "Unavailable", "reason": str(exc)},
            "articles": [],
        }

    explicit_research = research_explicit_entities(
        question=question,
        alpaca_api_key=alpaca_api_key,
        alpaca_secret_key=alpaca_secret_key,
        alpha_vantage_api_key=alpha_vantage_api_key,
        finnhub_api_key=finnhub_api_key,
        fmp_api_key=fmp_api_key,
    )

    return {
        "question": question,
        "independent_market_discovery": discovery,
        "independent_market_news": market_news,
        "independent_ticker_research": explicit_research,
        "momo_scan_reference": (momo_scan_reference or [])[:30],
        "momo_market_context_reference": market_context,
        "research_scope_note": (
            "Independent research is primary. MomoPro scan/context is supplied "
            "only as an additional reference. The discovery pass uses broad "
            "external market feeds and web research, but does not claim to "
            "exhaustively evaluate every listed security."
        ),
    }

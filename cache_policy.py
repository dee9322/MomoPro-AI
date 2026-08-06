"""Central cache/freshness policy used by pages and data providers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CacheRule:
    ttl_seconds: int
    stale_while_revalidate: bool = True
    persist_saved_value: bool = True


DEFAULT_CACHE_POLICY: Mapping[str, CacheRule] = {
    "market_context": CacheRule(5 * 60),
    "scanner": CacheRule(15 * 60),
    "news": CacheRule(10 * 60),
    "company_profile": CacheRule(7 * 24 * 60 * 60),
    "sec_filings": CacheRule(60 * 60),
    "historical_candles": CacheRule(15 * 60),
    "relative_strength": CacheRule(30 * 60),
    "smart_money": CacheRule(30 * 60),
    "trade_intelligence": CacheRule(30 * 60),
    "ai_research": CacheRule(30 * 24 * 60 * 60, stale_while_revalidate=False),
    "webull_snapshot": CacheRule(5 * 60),
}


def ttl_seconds(resource: str, fallback: int = 900) -> int:
    return DEFAULT_CACHE_POLICY.get(resource, CacheRule(fallback)).ttl_seconds


def ttl_minutes(resource: str, fallback: int = 15) -> int:
    return max(1, ttl_seconds(resource, fallback * 60) // 60)

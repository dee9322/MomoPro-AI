from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
import time
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import RLock

import pandas as pd
import requests

from cloud_storage import cloud_available, load_document, save_document
from float_intelligence import get_float_intelligence
from sec_intelligence import get_company_profile

_CACHE_PATH = Path(__file__).with_name("company_metadata_cache.json")
_METADATA_TTL_DAYS = 30
_METADATA_BUCKET = "company_metadata_cache"
_CACHE_LOCK = RLock()

# Broad SIC groupings. This is intentionally deterministic and provider-neutral.
_SIC_SECTORS = (
    (100, 999, "Agriculture"),
    (1000, 1499, "Materials"),
    (1500, 1799, "Industrials"),
    (2000, 2399, "Consumer Defensive"),
    (2400, 2799, "Industrials"),
    (2800, 2899, "Healthcare"),
    (2900, 2999, "Energy"),
    (3000, 3999, "Industrials"),
    (4000, 4899, "Industrials"),
    (4900, 4999, "Utilities"),
    (5000, 5199, "Consumer Cyclical"),
    (5200, 5999, "Consumer Cyclical"),
    (6000, 6799, "Financial Services"),
    (7000, 7299, "Communication Services"),
    (7300, 7399, "Technology"),
    (7500, 7999, "Consumer Cyclical"),
    (8000, 8099, "Healthcare"),
    (8100, 8999, "Industrials"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_local_cache() -> dict[str, Any]:
    try:
        raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _read_cache() -> dict[str, Any]:
    local = _read_local_cache()
    value = load_document(_METADATA_BUCKET, local) if cloud_available() else local
    return value if isinstance(value, dict) else local


def _write_cache(cache: dict[str, Any]) -> None:
    # Multiple metadata workers may finish together. Merge under a lock so one
    # completed ticker can never overwrite another worker's freshly cached row.
    with _CACHE_LOCK:
        current = _read_local_cache()
        merged = dict(current)
        for symbol, incoming in cache.items():
            existing = merged.get(symbol)
            if not isinstance(existing, dict) or not isinstance(incoming, dict):
                merged[symbol] = incoming
                continue
            if str(incoming.get("cached_at") or "") >= str(existing.get("cached_at") or ""):
                merged[symbol] = incoming
        try:
            _CACHE_PATH.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            pass
        if cloud_available():
            save_document(_METADATA_BUCKET, merged)


def _sector_from_sic(value: Any) -> str:
    try:
        sic = int(str(value or "").strip())
    except (TypeError, ValueError):
        return "Unclassified"
    for low, high, label in _SIC_SECTORS:
        if low <= sic <= high:
            return label
    return "Unclassified"


def _fresh(record: dict[str, Any]) -> bool:
    try:
        fetched = datetime.fromisoformat(str(record.get("cached_at") or ""))
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return _utc_now() - fetched < timedelta(days=_METADATA_TTL_DAYS)
    except Exception:
        return False


def get_company_metadata(
    symbol: str,
    *,
    fmp_api_key: str | None = None,
    alpha_vantage_api_key: str | None = None,
    force_refresh: bool = False,
    persist: bool = True,
    lightweight: bool = False,
) -> dict[str, Any]:
    ticker = str(symbol or "").upper().strip()
    if not ticker:
        return {"symbol": "", "status": "Unavailable"}

    cache = _read_cache()
    cached = cache.get(ticker)
    if isinstance(cached, dict) and _fresh(cached) and not force_refresh:
        return cached

    sec = get_company_profile(ticker)
    float_data = {} if lightweight else get_float_intelligence(ticker, fmp_api_key, alpha_vantage_api_key)
    provider: dict[str, Any] = {}
    try:
        if not lightweight and alpha_vantage_api_key:
            response = requests.get(
                "https://www.alphavantage.co/query",
                params={"function": "OVERVIEW", "symbol": ticker, "apikey": alpha_vantage_api_key},
                timeout=20,
            )
            payload = response.json() if response.status_code == 200 else {}
            if isinstance(payload, dict) and payload.get("Symbol"):
                provider = payload
        if not lightweight and not provider and fmp_api_key:
            response = requests.get(
                "https://financialmodelingprep.com/stable/profile",
                params={"symbol": ticker, "apikey": fmp_api_key},
                timeout=20,
            )
            payload = response.json() if response.status_code == 200 else {}
            if isinstance(payload, list) and payload:
                provider = payload[0]
            elif isinstance(payload, dict):
                provider = payload
    except Exception:
        provider = {}

    def _number(value: Any) -> float | None:
        try:
            return float(value) if value not in (None, "", "None") else None
        except (TypeError, ValueError):
            return None

    record = {
        "symbol": ticker,
        "status": "Available" if sec.get("status") in {"Available", "Partial"} else "Unavailable",
        "company": provider.get("Name") or provider.get("companyName") or sec.get("company") or ticker,
        "sector": provider.get("Sector") or provider.get("sector") or sec.get("sector") or _sector_from_sic(sec.get("sic")),
        "industry": provider.get("Industry") or provider.get("industry") or sec.get("industry") or "Unclassified",
        "exchange": provider.get("Exchange") or provider.get("exchange") or sec.get("exchange") or "",
        "country": provider.get("Country") or provider.get("country") or ("United States" if sec.get("cik") else ""),
        "market_cap": _number(provider.get("MarketCapitalization") or provider.get("marketCap")),
        "float_shares": float_data.get("float_shares"),
        "shares_outstanding": float_data.get("shares_outstanding"),
        "sic": sec.get("sic") or "",
        "cik": sec.get("cik") or "",
        "cached_at": _utc_now().isoformat(),
    }
    cache[ticker] = record
    if persist:
        _write_cache(cache)
    return record


def cached_company_metadata(symbol: str) -> dict[str, Any] | None:
    record = _read_cache().get(str(symbol or "").upper().strip())
    return record if isinstance(record, dict) else None


def available_cached_sectors() -> list[str]:
    sectors = {
        str(item.get("sector") or "").strip()
        for item in _read_cache().values()
        if isinstance(item, dict)
    }
    return sorted(sector for sector in sectors if sector and sector != "Unclassified")


def attach_cached_metadata(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or "Symbol" not in frame.columns:
        return frame
    cache = _read_cache()
    enriched = frame.copy()
    for column in ("Company", "Sector", "Industry", "Exchange", "Country", "Market Cap", "Float", "Shares Outstanding"):
        if column not in enriched.columns:
            enriched[column] = None
    for index, symbol in enriched["Symbol"].items():
        item = cache.get(str(symbol).upper()) or {}
        enriched.at[index, "Company"] = item.get("company")
        enriched.at[index, "Sector"] = item.get("sector")
        enriched.at[index, "Industry"] = item.get("industry")
        enriched.at[index, "Exchange"] = item.get("exchange")
        enriched.at[index, "Country"] = item.get("country")
        enriched.at[index, "Market Cap"] = item.get("market_cap")
        enriched.at[index, "Float"] = item.get("float_shares")
        enriched.at[index, "Shares Outstanding"] = item.get("shares_outstanding")
    return enriched



def enrich_company_metadata(
    frame: pd.DataFrame,
    *,
    fmp_api_key: str | None = None,
    alpha_vantage_api_key: str | None = None,
    max_workers: int = 2,
) -> pd.DataFrame:
    """Attach cached metadata and automatically fetch missing scanner symbols.

    The scanner remains responsive on later reruns because every successful
    lookup is persisted in the shared metadata cache. Provider failures are
    isolated per ticker and never prevent the scan table from rendering.
    """
    if frame is None or frame.empty or "Symbol" not in frame.columns:
        return frame

    symbols = [str(value or "").upper().strip() for value in frame["Symbol"].tolist()]
    symbols = list(dict.fromkeys(symbol for symbol in symbols if symbol))
    cache = _read_cache()
    missing = [symbol for symbol in symbols if not isinstance(cache.get(symbol), dict) or not _fresh(cache[symbol])]

    if missing:
        workers = max(1, min(int(max_workers or 1), 6, len(missing)))
        fetched: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    get_company_metadata,
                    symbol,
                    fmp_api_key=fmp_api_key,
                    alpha_vantage_api_key=alpha_vantage_api_key,
                    persist=False,
                    lightweight=True,
                ): symbol
                for symbol in missing
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    record = future.result()
                    if isinstance(record, dict):
                        fetched[symbol] = record
                except Exception:
                    # Retry once, gently, because SEC/provider throttling can leave
                    # a scanner row blank even though the ticker is valid.
                    try:
                        time.sleep(0.35)
                        record = get_company_metadata(
                            symbol,
                            fmp_api_key=fmp_api_key,
                            alpha_vantage_api_key=alpha_vantage_api_key,
                            persist=False,
                            lightweight=True,
                            force_refresh=True,
                        )
                        if isinstance(record, dict):
                            fetched[symbol] = record
                    except Exception:
                        # Metadata enrichment must never break the scanner.
                        pass
        if fetched:
            cache.update(fetched)
            _write_cache(cache)

    return attach_cached_metadata(frame)

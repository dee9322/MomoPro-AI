from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

import pandas as pd
import requests

from cloud_storage import cloud_available, load_document, save_document
from float_intelligence import get_float_intelligence
from sec_intelligence import get_company_profile

_CACHE_PATH = Path(__file__).with_name("company_metadata_cache.json")
_METADATA_BUCKET = "company_metadata_cache"
_COMPLETE_TTL = timedelta(days=30)
_INCOMPLETE_TTL = timedelta(hours=6)
_CACHE_LOCK = RLock()
_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 MomoProAI/0.98.4 contact: dbardwell9322@gmail.com",
    "Accept": "application/json,text/plain,*/*",
}

_SIC_SECTORS = (
    (100, 999, "Agriculture"), (1000, 1499, "Materials"),
    (1500, 1799, "Industrials"), (2000, 2399, "Consumer Defensive"),
    (2400, 2799, "Industrials"), (2800, 2899, "Healthcare"),
    (2900, 2999, "Energy"), (3000, 3999, "Industrials"),
    (4000, 4899, "Industrials"), (4900, 4999, "Utilities"),
    (5000, 5199, "Consumer Cyclical"), (5200, 5999, "Consumer Cyclical"),
    (6000, 6799, "Financial Services"), (7000, 7299, "Communication Services"),
    (7300, 7399, "Technology"), (7500, 7999, "Consumer Cyclical"),
    (8000, 8099, "Healthcare"), (8100, 8999, "Industrials"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _number(value: Any) -> float | None:
    if value in (None, "", "None", "N/A", "—", "--"):
        return None
    if isinstance(value, str):
        text = value.replace("$", "").replace(",", "").strip()
        multiplier = 1.0
        if text and text[-1:].upper() in {"K", "M", "B", "T"}:
            multiplier = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[text[-1].upper()]
            text = text[:-1]
        try:
            return float(text) * multiplier
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(*values: Any) -> float | None:
    for value in values:
        parsed = _number(value)
        if parsed is not None:
            return parsed
    return None


def _read_local_cache() -> dict[str, Any]:
    try:
        raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _read_cache() -> dict[str, Any]:
    with _CACHE_LOCK:
        local = _read_local_cache()
        try:
            value = load_document(_METADATA_BUCKET, local) if cloud_available() else local
        except Exception:
            value = local
        return value if isinstance(value, dict) else local


def _write_cache(cache: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        try:
            _CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            pass
        if cloud_available():
            try:
                save_document(_METADATA_BUCKET, cache)
            except Exception:
                pass


def _record_complete(record: dict[str, Any]) -> bool:
    return all(_number(record.get(key)) is not None for key in ("market_cap", "shares_outstanding")) and bool(record.get("company"))


def _fresh(record: dict[str, Any]) -> bool:
    try:
        fetched = datetime.fromisoformat(str(record.get("cached_at") or ""))
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        ttl = _COMPLETE_TTL if _record_complete(record) else _INCOMPLETE_TTL
        return _utc_now() - fetched < ttl
    except Exception:
        return False


def _sector_from_sic(value: Any) -> str:
    try:
        sic = int(str(value or "").strip())
    except (TypeError, ValueError):
        return "Unclassified"
    for low, high, label in _SIC_SECTORS:
        if low <= sic <= high:
            return label
    return "Unclassified"


def _safe_json(url: str, *, params: dict[str, Any] | None = None, timeout: int = 12) -> Any:
    try:
        response = requests.get(url, params=params, headers=_HTTP_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {}


def _recursive_values(value: Any, wanted: set[str]) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace(" ", "").replace("_", "")
            if normalized in wanted:
                if isinstance(item, dict) and "value" in item:
                    found.append(item.get("value"))
                else:
                    found.append(item)
            found.extend(_recursive_values(item, wanted))
    elif isinstance(value, list):
        for item in value:
            found.extend(_recursive_values(item, wanted))
    return found


def _provider_value(payloads: Iterable[Any], *keys: str) -> Any:
    wanted = {key.lower().replace(" ", "").replace("_", "") for key in keys}
    for payload in payloads:
        values = _recursive_values(payload, wanted)
        for value in values:
            if value not in (None, "", "N/A", "—", "--"):
                return value
    return None


@lru_cache(maxsize=1000)
def _sec_shares_outstanding(cik: str) -> float | None:
    cik_text = str(cik or "").zfill(10)
    if not cik_text.strip("0"):
        return None
    payload = _safe_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_text}.json", timeout=18)
    facts = (payload or {}).get("facts", {}).get("dei", {}) if isinstance(payload, dict) else {}
    candidates: list[tuple[str, float]] = []
    for fact_name in ("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"):
        rows = ((facts.get(fact_name) or {}).get("units", {}) or {}).get("shares") or []
        for row in rows:
            parsed = _number(row.get("val"))
            if parsed is not None:
                candidates.append((str(row.get("filed") or row.get("end") or ""), parsed))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _public_market_payloads(symbol: str) -> list[Any]:
    ticker = symbol.upper()
    # These public endpoints are fallbacks. Failure of any endpoint is isolated.
    yahoo = _safe_json("https://query1.finance.yahoo.com/v7/finance/quote", params={"symbols": ticker})
    nasdaq_summary = _safe_json(f"https://api.nasdaq.com/api/quote/{ticker}/summary", params={"assetclass": "stocks"})
    nasdaq_stats = _safe_json(f"https://api.nasdaq.com/api/quote/{ticker}/info", params={"assetclass": "stocks"})
    return [yahoo, nasdaq_summary, nasdaq_stats]


def _paid_provider_payloads(symbol: str, fmp_api_key: str | None, alpha_vantage_api_key: str | None) -> list[Any]:
    payloads: list[Any] = []
    if alpha_vantage_api_key:
        payloads.append(_safe_json("https://www.alphavantage.co/query", params={"function": "OVERVIEW", "symbol": symbol, "apikey": alpha_vantage_api_key}))
    if fmp_api_key:
        payloads.append(_safe_json("https://financialmodelingprep.com/stable/profile", params={"symbol": symbol, "apikey": fmp_api_key}))
        payloads.append(_safe_json("https://financialmodelingprep.com/stable/shares-float", params={"symbol": symbol, "apikey": fmp_api_key}))
    return payloads


def get_company_metadata(symbol: str, *, fmp_api_key: str | None = None, alpha_vantage_api_key: str | None = None, force_refresh: bool = False, _persist: bool = True) -> dict[str, Any]:
    ticker = str(symbol or "").upper().strip()
    if not ticker:
        return {"symbol": "", "status": "Unavailable"}
    cache = _read_cache()
    cached = cache.get(ticker)
    if isinstance(cached, dict) and _fresh(cached) and not force_refresh:
        return cached

    sec = get_company_profile(ticker)
    float_data = get_float_intelligence(ticker, fmp_api_key, alpha_vantage_api_key)
    payloads = _paid_provider_payloads(ticker, fmp_api_key, alpha_vantage_api_key) + _public_market_payloads(ticker)

    company = _provider_value(payloads, "longName", "shortName", "Name", "companyName") or sec.get("company") or ticker
    sector = _provider_value(payloads, "Sector", "sector") or sec.get("sector") or _sector_from_sic(sec.get("sic"))
    industry = _provider_value(payloads, "Industry", "industry") or sec.get("industry") or "Unclassified"
    exchange = _provider_value(payloads, "fullExchangeName", "exchange", "Exchange") or sec.get("exchange") or ""
    country = _provider_value(payloads, "Country", "country") or ("United States" if sec.get("cik") else "")

    outstanding = _first_number(
        float_data.get("shares_outstanding"),
        _provider_value(payloads, "sharesOutstanding", "SharesOutstanding", "shareOutstanding", "totalSharesOutstanding"),
        _sec_shares_outstanding(sec.get("cik")),
    )
    float_shares = _first_number(
        float_data.get("float_shares"),
        _provider_value(payloads, "floatShares", "SharesFloat", "publicFloat", "shareFloat"),
    )
    market_cap = _first_number(
        _provider_value(payloads, "marketCap", "MarketCapitalization", "marketCapitalization", "MarketCap"),
    )

    record = {
        "symbol": ticker,
        "status": "Available" if company or sec.get("cik") else "Unavailable",
        "company": company,
        "sector": sector,
        "industry": industry,
        "exchange": exchange,
        "country": country,
        "market_cap": market_cap,
        "float_shares": float_shares,
        "shares_outstanding": outstanding,
        "sic": sec.get("sic") or "",
        "cik": sec.get("cik") or "",
        "sources": ["SEC", "FMP/Alpha Vantage" if (fmp_api_key or alpha_vantage_api_key) else None, "Yahoo/Nasdaq fallback"],
        "cached_at": _utc_now().isoformat(),
    }
    record["sources"] = [source for source in record["sources"] if source]
    cache[ticker] = record
    if _persist:
        _write_cache(cache)
    return record


def enrich_company_metadata_batch(symbols: list[str], *, fmp_api_key: str | None = None, alpha_vantage_api_key: str | None = None, force_refresh: bool = False, max_workers: int = 4) -> dict[str, dict[str, Any]]:
    tickers = list(dict.fromkeys(str(symbol or "").upper().strip() for symbol in symbols if str(symbol or "").strip()))
    cache = _read_cache()
    results: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for ticker in tickers:
        record = cache.get(ticker)
        if isinstance(record, dict) and _fresh(record) and not force_refresh:
            results[ticker] = record
        else:
            missing.append(ticker)
    if missing:
        workers = max(1, min(int(max_workers or 1), 4, len(missing)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            jobs = {executor.submit(get_company_metadata, ticker, fmp_api_key=fmp_api_key, alpha_vantage_api_key=alpha_vantage_api_key, force_refresh=force_refresh, _persist=False): ticker for ticker in missing}
            for future in as_completed(jobs):
                ticker = jobs[future]
                try:
                    record = future.result()
                except Exception:
                    record = cache.get(ticker) or {"symbol": ticker, "status": "Unavailable", "cached_at": _utc_now().isoformat()}
                results[ticker] = record
        cache.update(results)
        _write_cache(cache)
    return results


def cached_company_metadata(symbol: str) -> dict[str, Any] | None:
    record = _read_cache().get(str(symbol or "").upper().strip())
    return record if isinstance(record, dict) else None


def available_cached_sectors() -> list[str]:
    sectors = {str(item.get("sector") or "").strip() for item in _read_cache().values() if isinstance(item, dict)}
    return sorted(sector for sector in sectors if sector and sector != "Unclassified")


def attach_cached_metadata(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty or "Symbol" not in frame.columns:
        return frame
    cache = _read_cache()
    enriched = frame.copy()
    columns = ("Company", "Sector", "Industry", "Exchange", "Country", "Market Cap", "Float", "Shares Outstanding")
    for column in columns:
        if column not in enriched.columns:
            enriched[column] = None
    for index, symbol in enriched["Symbol"].items():
        item = cache.get(str(symbol).upper()) or {}
        values = {
            "Company": item.get("company"), "Sector": item.get("sector"), "Industry": item.get("industry"),
            "Exchange": item.get("exchange"), "Country": item.get("country"), "Market Cap": _number(item.get("market_cap")),
            "Float": _number(item.get("float_shares")), "Shares Outstanding": _number(item.get("shares_outstanding")),
        }
        for column, value in values.items():
            if value is not None and value != "":
                enriched.at[index, column] = value
    return enriched


def enrich_company_metadata(frame: pd.DataFrame, *, fmp_api_key: str | None = None, alpha_vantage_api_key: str | None = None, max_workers: int = 2) -> pd.DataFrame:
    if frame is None or frame.empty or "Symbol" not in frame.columns:
        return frame
    enrich_company_metadata_batch(frame["Symbol"].astype(str).tolist(), fmp_api_key=fmp_api_key, alpha_vantage_api_key=alpha_vantage_api_key, max_workers=max_workers)
    return attach_cached_metadata(frame)

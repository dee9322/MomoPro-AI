from __future__ import annotations

from datetime import date, timedelta
from typing import Any
import re

import requests


_OPTION_SYMBOL = re.compile(r"^([A-Z0-9]{1,8})(\d{6})([CP])(\d{8})$")
MAX_PAGES = 10


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def _pick(mapping: dict[str, Any] | None, *names: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return None


def _parse_contract(symbol: str) -> dict[str, Any]:
    match = _OPTION_SYMBOL.match(symbol or "")
    if not match:
        return {"contract": symbol, "type": "—", "expiration": None, "strike": None}
    _, expiry, cp, strike_raw = match.groups()
    return {
        "contract": symbol,
        "type": "Call" if cp == "C" else "Put",
        "expiration": f"20{expiry[:2]}-{expiry[2:4]}-{expiry[4:6]}",
        "strike": int(strike_raw) / 1000,
    }


def _friendly_unavailable(message: str) -> dict[str, Any]:
    return {
        "status": "Unavailable",
        "score": None,
        "bias": "Unavailable",
        "summary": message,
        "active_contracts": [],
        "data_source": "Alpaca Indicative",
        "data_quality": "Unavailable",
    }


def _fetch_all_snapshots(
    symbol: str,
    headers: dict[str, str],
    base_params: dict[str, Any],
) -> tuple[dict[str, Any], int, bool]:
    snapshots: dict[str, Any] = {}
    page_token: str | None = None
    page_count = 0
    truncated = False

    while page_count < MAX_PAGES:
        params = dict(base_params)
        if page_token:
            params["page_token"] = page_token
        response = requests.get(
            f"https://data.alpaca.markets/v1beta1/options/snapshots/{symbol.upper()}",
            params=params,
            headers=headers,
            timeout=30,
        )
        if response.status_code in (401, 403):
            raise PermissionError
        if response.status_code == 429:
            raise RuntimeError("rate_limited")
        response.raise_for_status()
        payload = response.json()

        page = payload.get("snapshots") or payload.get("data") or {}
        if isinstance(page, list):
            page = {
                str(item.get("symbol") or item.get("contract_symbol") or index): item
                for index, item in enumerate(page)
                if isinstance(item, dict)
            }
        if isinstance(page, dict):
            snapshots.update(page)

        page_count += 1
        page_token = payload.get("next_page_token") or payload.get("nextPageToken")
        if not page_token:
            break
    else:
        truncated = bool(page_token)

    return snapshots, page_count, truncated


def get_options_activity(
    symbol: str,
    alpaca_api_key: str | None,
    alpaca_secret_key: str | None,
) -> dict[str, Any]:
    if not alpaca_api_key or not alpaca_secret_key:
        return _friendly_unavailable("Alpaca API credentials are missing.")

    today = date.today()
    params = {
        "feed": "indicative",
        "limit": 1000,
        "expiration_date_gte": today.isoformat(),
        "expiration_date_lte": (today + timedelta(days=45)).isoformat(),
    }
    headers = {
        "APCA-API-KEY-ID": alpaca_api_key,
        "APCA-API-SECRET-KEY": alpaca_secret_key,
    }

    try:
        snapshots, page_count, truncated = _fetch_all_snapshots(
            symbol,
            headers,
            params,
        )
    except PermissionError:
        return _friendly_unavailable(
            "Alpaca options data is not authorized for the connected account."
        )
    except RuntimeError:
        return _friendly_unavailable(
            "Alpaca options data is temporarily rate-limited. Try again shortly."
        )
    except (requests.RequestException, ValueError):
        return _friendly_unavailable(
            "Alpaca's indicative options feed could not be reached right now."
        )

    if not snapshots:
        return _friendly_unavailable(
            "No active option-chain snapshots were returned for this ticker."
        )

    call_trade_size = 0.0
    put_trade_size = 0.0
    call_contracts = 0
    put_contracts = 0
    iv_values: list[float] = []
    candidates: list[dict[str, Any]] = []
    expirations: dict[str, int] = {}

    for contract_symbol, snapshot in snapshots.items():
        if not isinstance(snapshot, dict):
            continue
        parsed = _parse_contract(str(contract_symbol))
        option_type = parsed["type"]
        if option_type == "Call":
            call_contracts += 1
        elif option_type == "Put":
            put_contracts += 1
        else:
            continue

        latest_trade = _pick(snapshot, "latestTrade", "latest_trade") or {}
        latest_quote = _pick(snapshot, "latestQuote", "latest_quote") or {}
        greeks = _pick(snapshot, "greeks") or {}

        trade_size = _number(_pick(latest_trade, "s", "size")) or 0.0
        trade_price = _number(_pick(latest_trade, "p", "price"))
        bid_price = _number(_pick(latest_quote, "bp", "bid_price"))
        ask_price = _number(_pick(latest_quote, "ap", "ask_price"))
        bid_size = _number(_pick(latest_quote, "bs", "bid_size")) or 0.0
        ask_size = _number(_pick(latest_quote, "as", "ask_size")) or 0.0
        iv = _number(_pick(snapshot, "impliedVolatility", "implied_volatility"))
        delta = _number(_pick(greeks, "delta"))

        if option_type == "Call":
            call_trade_size += trade_size
        else:
            put_trade_size += trade_size

        if iv is not None and 0 <= iv <= 10:
            iv_values.append(iv)
        expiration = parsed.get("expiration")
        if expiration:
            expirations[expiration] = expirations.get(expiration, 0) + 1

        quote_size = max(bid_size, ask_size)
        activity_size = max(trade_size, quote_size)
        if activity_size >= 25:
            candidates.append({
                "contract": parsed["contract"],
                "type": option_type,
                "strike": parsed["strike"],
                "expiration": expiration,
                "latest_trade_size": round(trade_size) if trade_size else None,
                "latest_trade_price": round(trade_price, 2) if trade_price is not None else None,
                "bid": round(bid_price, 2) if bid_price is not None else None,
                "ask": round(ask_price, 2) if ask_price is not None else None,
                "largest_quote_size": round(quote_size) if quote_size else None,
                "implied_volatility": round(iv * 100, 1) if iv is not None else None,
                "delta": round(delta, 3) if delta is not None else None,
                "activity_size": activity_size,
            })

    total_trade_size = call_trade_size + put_trade_size
    call_share = call_trade_size / total_trade_size if total_trade_size > 0 else None
    put_call_ratio = put_trade_size / call_trade_size if call_trade_size > 0 else None

    if call_share is None:
        bias = "Insufficient Trade Activity"
        score = None
    elif call_share >= 0.62:
        bias = "Bullish Lean"
        score = round(min(75, 50 + (call_share - 0.5) * 80))
    elif call_share <= 0.38:
        bias = "Bearish Lean"
        score = round(max(25, 50 + (call_share - 0.5) * 80))
    else:
        bias = "Balanced"
        score = round(50 + (call_share - 0.5) * 40)

    candidates.sort(key=lambda item: item["activity_size"], reverse=True)
    for item in candidates:
        item.pop("activity_size", None)

    most_active_expiration = max(expirations, key=expirations.get) if expirations else None
    avg_iv = sum(iv_values) / len(iv_values) * 100 if iv_values else None

    return {
        "status": "Available",
        "score": max(0, min(100, score)) if score is not None else None,
        "bias": bias,
        "call_trade_size": round(call_trade_size) if call_trade_size else None,
        "put_trade_size": round(put_trade_size) if put_trade_size else None,
        "put_call_activity_ratio": round(put_call_ratio, 2) if put_call_ratio is not None else None,
        "call_contracts": call_contracts,
        "put_contracts": put_contracts,
        "contracts_analyzed": call_contracts + put_contracts,
        "average_implied_volatility_pct": round(avg_iv, 1) if avg_iv is not None else None,
        "most_active_expiration": most_active_expiration,
        "active_contract_count": len(candidates),
        "active_contracts": candidates[:12],
        "pages_loaded": page_count,
        "chain_truncated": truncated,
        "summary": (
            f"Alpaca's delayed indicative chain shows {bias.lower()} across "
            f"{call_contracts + put_contracts} contracts analyzed."
        ),
        "data_source": "Alpaca Indicative",
        "data_quality": "Delayed / Indicative",
        "disclaimer": (
            "This is a basic activity proxy from modified indicative quotes and delayed trades. "
            "It cannot determine opening versus closing transactions, sweep direction, or true "
            "institutional order flow."
        ),
    }

from __future__ import annotations

from typing import Any

import requests


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def get_options_activity(symbol: str, alpha_vantage_api_key: str | None) -> dict[str, Any]:
    """Analyze the most recent available Alpha Vantage options snapshot.

    Realtime options may require a paid entitlement. The function fails softly
    and clearly reports when the connected plan does not provide the dataset.
    """
    if not alpha_vantage_api_key:
        return {"status": "Unavailable", "summary": "Alpha Vantage API key is missing."}

    params = {
        "function": "HISTORICAL_OPTIONS",
        "symbol": symbol.upper(),
        "apikey": alpha_vantage_api_key,
    }
    response = requests.get("https://www.alphavantage.co/query", params=params, timeout=25)
    response.raise_for_status()
    payload = response.json()

    message = payload.get("Information") or payload.get("Note") or payload.get("Error Message")
    rows = payload.get("data") or payload.get("options") or []
    if not isinstance(rows, list) or not rows:
        return {
            "status": "Unavailable",
            "summary": message or "Options data was not returned by the connected plan.",
        }

    call_volume = put_volume = call_oi = put_oi = 0.0
    unusual: list[dict[str, Any]] = []

    for row in rows:
        option_type = str(row.get("type") or row.get("option_type") or "").lower()
        volume = _number(row.get("volume")) or 0
        open_interest = _number(row.get("open_interest") or row.get("openInterest")) or 0
        iv = _number(row.get("implied_volatility") or row.get("impliedVolatility"))
        ratio = volume / open_interest if open_interest > 0 else (volume if volume > 0 else 0)

        if option_type == "call":
            call_volume += volume
            call_oi += open_interest
        elif option_type == "put":
            put_volume += volume
            put_oi += open_interest

        if volume >= 100 and ratio >= 1.5:
            unusual.append({
                "contract": row.get("contractID") or row.get("contract") or "—",
                "type": option_type.title() or "—",
                "strike": _number(row.get("strike")),
                "expiration": row.get("expiration") or row.get("expiration_date"),
                "volume": round(volume),
                "open_interest": round(open_interest),
                "volume_oi_ratio": round(ratio, 2),
                "implied_volatility": round(iv, 4) if iv is not None else None,
            })

    total_volume = call_volume + put_volume
    put_call_volume = put_volume / call_volume if call_volume > 0 else None
    call_share = call_volume / total_volume if total_volume > 0 else 0.5
    score = round(max(0, min(100, 50 + (call_share - 0.5) * 80 + min(len(unusual) * 3, 20))))

    if put_call_volume is None:
        bias = "Unavailable"
    elif put_call_volume <= 0.70:
        bias = "Bullish"
    elif put_call_volume >= 1.30:
        bias = "Bearish"
    else:
        bias = "Balanced"

    unusual.sort(key=lambda item: (item["volume_oi_ratio"], item["volume"]), reverse=True)
    return {
        "status": "Available",
        "score": score,
        "bias": bias,
        "call_volume": round(call_volume),
        "put_volume": round(put_volume),
        "put_call_volume_ratio": round(put_call_volume, 2) if put_call_volume is not None else None,
        "call_open_interest": round(call_oi),
        "put_open_interest": round(put_oi),
        "unusual_contract_count": len(unusual),
        "unusual_contracts": unusual[:10],
        "summary": f"Options volume bias is {bias.lower()} with {len(unusual)} unusual volume/open-interest candidate(s).",
        "disclaimer": "Options signals are screening indicators, not proof of informed trading. Historical or delayed data may be returned depending on the API plan.",
    }

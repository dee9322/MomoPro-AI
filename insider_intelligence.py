from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests


def _number(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None


def _safe_get(url: str, params: dict[str, Any]) -> Any:
    try:
        response = requests.get(url, params=params, timeout=25)
        if response.status_code != 200:
            return None
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def _finnhub_trades(symbol: str, api_key: str | None) -> list[dict[str, Any]]:
    if not api_key:
        return []
    payload = _safe_get(
        "https://finnhub.io/api/v1/stock/insider-transactions",
        {"symbol": symbol.upper(), "token": api_key},
    )
    if not isinstance(payload, dict):
        return []
    rows = payload.get("data", [])
    return rows if isinstance(rows, list) else []


def _fmp_trades(symbol: str, api_key: str | None) -> list[dict[str, Any]]:
    if not api_key:
        return []
    payload = _safe_get(
        "https://financialmodelingprep.com/stable/insider-trading/search",
        {"symbol": symbol.upper(), "page": 0, "limit": 100, "apikey": api_key},
    )
    return payload if isinstance(payload, list) else []


def _normalized_type(row: dict[str, Any]) -> str:
    raw = str(
        row.get("transactionType")
        or row.get("transaction_type")
        or row.get("acquisitionOrDisposition")
        or row.get("acquisition_or_disposal")
        or row.get("transactionCode")
        or row.get("transaction_code")
        or ""
    ).strip()
    return raw


def get_insider_activity(
    symbol: str,
    finnhub_api_key: str | None,
    fmp_api_key: str | None,
) -> dict[str, Any]:
    rows = _finnhub_trades(symbol, finnhub_api_key)
    source = "Finnhub"
    if not rows:
        rows = _fmp_trades(symbol, fmp_api_key)
        source = "FMP"

    if not rows:
        return {
            "status": "Unavailable",
            "score": None,
            "transactions": [],
            "summary": "No recent insider transaction data was returned by the connected providers.",
            "display_message": "No recent insider activity found from connected providers.",
        }

    cutoff = datetime.utcnow().date() - timedelta(days=180)
    transactions: list[dict[str, Any]] = []
    purchase_value = sale_value = 0.0

    for row in rows:
        date_text = (
            row.get("transactionDate")
            or row.get("transaction_date")
            or row.get("filingDate")
            or row.get("filing_date")
        )
        try:
            date_value = datetime.fromisoformat(str(date_text)[:10]).date()
        except Exception:
            date_value = None
        if date_value and date_value < cutoff:
            continue

        transaction_type = _normalized_type(row)
        transaction_lower = transaction_type.lower()
        shares_value = _number(
            row.get("securitiesTransacted")
            or row.get("share")
            or row.get("shares")
            or row.get("shares_traded")
            or row.get("change")
        )
        shares = abs(shares_value) if shares_value is not None else None
        price = _number(row.get("price") or row.get("transaction_price"))
        value = shares * price if shares is not None and price is not None else None

        code = transaction_type.upper()
        is_buy = (
            any(token in transaction_lower for token in ("purchase", "buy", "acquisition"))
            or code in {"P", "A"}
        ) and not any(token in transaction_lower for token in ("sale", "sell", "disposition"))
        is_sell = (
            any(token in transaction_lower for token in ("sale", "sell", "disposition"))
            or code in {"S", "D"}
        )

        if is_buy and value is not None:
            purchase_value += value
        elif is_sell and value is not None:
            sale_value += value

        transactions.append(
            {
                "date": str(date_text)[:10] if date_text else None,
                "name": row.get("reportingName") or row.get("name") or row.get("insider_name") or "—",
                "role": row.get("typeOfOwner") or row.get("title") or row.get("executive_title") or "—",
                "transaction": transaction_type or "—",
                "shares": round(shares) if shares is not None else None,
                "price": round(price, 2) if price is not None else None,
                "estimated_value": round(value, 2) if value is not None else None,
                "source": source,
            }
        )

    transactions = transactions[:20]
    if not transactions:
        return {
            "status": "Unavailable",
            "score": None,
            "transactions": [],
            "summary": "No recent insider transactions were found in the last 180 days.",
            "display_message": "No recent insider activity found.",
        }

    total = purchase_value + sale_value
    net = purchase_value - sale_value
    score = round(max(0, min(100, 50 + (net / total) * 40))) if total > 0 else 50

    if purchase_value > sale_value * 1.25:
        verdict = "Net Buying"
    elif sale_value > purchase_value * 1.25:
        verdict = "Net Selling"
    else:
        verdict = "Balanced / Inconclusive"

    return {
        "status": "Available",
        "score": score,
        "verdict": verdict,
        "purchase_value": round(purchase_value, 2),
        "sale_value": round(sale_value, 2),
        "net_value": round(net, 2),
        "transaction_count": len(transactions),
        "transactions": transactions,
        "source": source,
        "data_quality": "Reported / Delayed",
        "summary": f"Recent reported insider activity is {verdict.lower()} based on available transactions.",
        "disclaimer": "Insider sales can be routine or plan-based; review the original filing before drawing conclusions.",
    }

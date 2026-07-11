from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmp_trades(symbol: str, api_key: str | None) -> list[dict[str, Any]]:
    if not api_key:
        return []
    response = requests.get(
        "https://financialmodelingprep.com/stable/insider-trading/search",
        params={"symbol": symbol.upper(), "page": 0, "limit": 100, "apikey": api_key},
        timeout=25,
    )
    if response.status_code != 200:
        return []
    data = response.json()
    return data if isinstance(data, list) else []


def _alpha_trades(symbol: str, api_key: str | None) -> list[dict[str, Any]]:
    if not api_key:
        return []
    response = requests.get(
        "https://www.alphavantage.co/query",
        params={"function": "INSIDER_TRANSACTIONS", "symbol": symbol.upper(), "apikey": api_key},
        timeout=25,
    )
    if response.status_code != 200:
        return []
    payload = response.json()
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def get_insider_activity(symbol: str, fmp_api_key: str | None, alpha_vantage_api_key: str | None) -> dict[str, Any]:
    rows = _fmp_trades(symbol, fmp_api_key) or _alpha_trades(symbol, alpha_vantage_api_key)
    if not rows:
        return {"status": "Unavailable", "summary": "No insider transaction data was returned by the connected providers."}

    cutoff = datetime.utcnow().date() - timedelta(days=180)
    transactions: list[dict[str, Any]] = []
    purchase_value = sale_value = 0.0

    for row in rows:
        date_text = row.get("transactionDate") or row.get("transaction_date") or row.get("filingDate") or row.get("filing_date")
        try:
            date_value = datetime.fromisoformat(str(date_text)[:10]).date()
        except Exception:
            date_value = None
        if date_value and date_value < cutoff:
            continue

        transaction_type = str(row.get("transactionType") or row.get("transaction_type") or row.get("acquisition_or_disposal") or "").lower()
        shares = abs(_number(row.get("securitiesTransacted") or row.get("shares") or row.get("shares_traded")))
        price = _number(row.get("price") or row.get("transaction_price"))
        value = shares * price
        is_buy = any(token in transaction_type for token in ("purchase", "buy", "acquisition", "a")) and "sale" not in transaction_type
        is_sell = any(token in transaction_type for token in ("sale", "sell", "disposition", "d"))
        if is_buy:
            purchase_value += value
        elif is_sell:
            sale_value += value

        transactions.append({
            "date": str(date_text)[:10] if date_text else None,
            "name": row.get("reportingName") or row.get("name") or row.get("insider_name") or "—",
            "role": row.get("typeOfOwner") or row.get("title") or row.get("executive_title") or "—",
            "transaction": row.get("transactionType") or row.get("transaction_type") or row.get("acquisition_or_disposal") or "—",
            "shares": round(shares),
            "price": round(price, 2) if price else None,
            "estimated_value": round(value, 2) if value else None,
        })

    transactions = transactions[:20]
    total = purchase_value + sale_value
    net = purchase_value - sale_value
    if total > 0:
        score = round(max(0, min(100, 50 + (net / total) * 40)))
    else:
        score = 50
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
        "summary": f"Recent reported insider activity is {verdict.lower()} based on available transactions.",
        "disclaimer": "Insider sales can be routine or plan-based; each filing should be reviewed before drawing conclusions.",
    }

from __future__ import annotations

from typing import Any, Dict, List

from opportunity_engine import calculate_opportunity_score
from watchlist_models import WatchlistItem, utc_now


def _pick(row: Dict[str, Any], *keys: str, default=None):
    for key in keys:
        value = row.get(key)
        if value is not None and str(value) != "nan":
            return value
    return default


def refresh_item_from_scan(item: WatchlistItem, row: Dict[str, Any]) -> List[Dict[str, Any]]:
    previous = dict(item.ai_state or {})
    events: List[Dict[str, Any]] = []
    opportunity, reason, components = calculate_opportunity_score(row)
    confidence = _pick(row, "AI Confidence", "Confidence %", "Confidence")
    grade = _pick(row, "Grade", default="—")
    setup = _pick(row, "Setup", default="—")

    item.company = str(_pick(row, "Company", "Name", default=item.company) or item.company)
    item.sector = str(_pick(row, "Sector", default=item.sector) or item.sector)
    item.industry = str(_pick(row, "Industry", default=item.industry) or item.industry)
    item.technical = {
        "price": _pick(row, "Price", "Close"),
        "grade": grade,
        "momo_score": _pick(row, "Momo Score"),
        "dee_fit": _pick(row, "Dee Fit"),
        "confidence": confidence,
        "setup": setup,
        "relative_strength": _pick(row, "Relative Strength", "RS Score"),
        "ema21": _pick(row, "EMA21", "EMA 21"),
        "ema50": _pick(row, "EMA50", "EMA 50"),
        "ema200": _pick(row, "EMA200", "EMA 200"),
        "rvol": _pick(row, "RVOL"),
        "atr_pct": _pick(row, "ATR %", "ATR%"),
        "risk_reward": _pick(row, "Risk Reward"),
    }
    item.intelligence = {
        "market_context": _pick(row, "Market Context"),
        "news_summary": _pick(row, "News Summary"),
        "smart_money": _pick(row, "Smart Money"),
        "trading_intelligence": _pick(row, "Trading Intelligence"),
        "ai_rating": _pick(row, "AI Rating", default=grade),
        "ai_confidence": confidence,
    }

    status = "Thesis untested"
    thesis_lower = item.thesis.lower()
    setup_lower = str(setup).lower()
    if item.thesis:
        if "ema21" in thesis_lower and any(word in setup_lower for word in ("reclaim", "retest")):
            status = "Thesis strengthening"
        elif opportunity < 35:
            status = "Thesis weakening"
        else:
            status = "Thesis still developing"
    if opportunity >= 85:
        recommendation = "Buy candidate"
    elif opportunity >= 65:
        recommendation = "Watch closely"
    elif opportunity >= 45:
        recommendation = "Wait"
    else:
        recommendation = "Avoid for now"

    item.ai_state = {
        "opportunity_score": opportunity,
        "opportunity_reason": reason,
        "opportunity_components": components,
        "thesis_status": status,
        "recommendation": recommendation,
        "last_updated": utc_now(),
    }

    comparisons = [
        ("Opportunity Score", previous.get("opportunity_score"), opportunity),
        ("AI Confidence", previous.get("confidence"), confidence),
        ("Grade", previous.get("grade"), grade),
        ("Setup", previous.get("setup"), setup),
        ("Thesis Status", previous.get("thesis_status"), status),
        ("Recommendation", previous.get("recommendation"), recommendation),
    ]
    for label, old, new in comparisons:
        if old is not None and new is not None and str(old) != str(new):
            events.append({"timestamp": utc_now(), "event": f"{label} changed", "details": f"{old} → {new}"})

    item.ai_state.update({"confidence": confidence, "grade": grade, "setup": setup})
    item.timeline.extend(events)
    return events


def build_morning_brief(items: List[WatchlistItem]) -> Dict[str, Any]:
    ranked = sorted(items, key=lambda item: item.ai_state.get("opportunity_score", 0) or 0, reverse=True)
    improved = sum(1 for item in items if "strengthening" in str(item.ai_state.get("thesis_status", "")).lower())
    weakened = sum(1 for item in items if any(x in str(item.ai_state.get("thesis_status", "")).lower() for x in ("weakening", "invalid")))
    top = ranked[0] if ranked else None
    return {
        "count": len(items), "improved": improved, "weakened": weakened,
        "top_symbol": top.symbol if top else None,
        "top_opportunity": top.ai_state.get("opportunity_score") if top else None,
        "top_confidence": top.technical.get("confidence") if top else None,
        "ranked": ranked,
    }

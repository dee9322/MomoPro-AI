from __future__ import annotations

from typing import Any, Dict, List

from opportunity_engine import calculate_opportunity_score
from sec_intelligence import get_company_profile
from watchlist_models import WatchlistItem, utc_now


def _pick(row: Dict[str, Any], *keys: str, default=None):
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).lower() != "nan":
            return value
    return default


def _number(value: Any) -> float | None:
    try:
        if value is not None and str(value).lower() != "nan":
            return float(value)
    except (TypeError, ValueError):
        pass
    return None


def _report_timestamp(report: Dict[str, Any]) -> str:
    return str(report.get("generated_at") or report.get("timestamp") or utc_now())


def sync_ai_report_to_item(item: WatchlistItem, report: Dict[str, Any] | None) -> bool:
    """Persist the latest independent AI report into a living profile."""
    if not isinstance(report, dict) or not report:
        return False

    previous_confidence = item.ai_state.get("ai_confidence")
    confidence = _number(report.get("confidence"))
    timestamp = _report_timestamp(report)
    item.intelligence = dict(item.intelligence or {})
    item.intelligence["independent_ai"] = {
        "status": "Available",
        "generated_at": timestamp,
        "confidence": confidence,
        "sentiment": report.get("sentiment"),
        "independent_action": report.get("independent_action"),
        "conviction": report.get("conviction"),
        "risk_level": report.get("risk_level"),
        "final_rating": report.get("final_rating"),
        "executive_summary": report.get("executive_summary"),
        "action_plan": report.get("action_plan"),
        "user_strategy_fit": report.get("user_strategy_fit"),
        "thesis_confirmations": report.get("thesis_confirmations") or report.get("bull_case"),
        "thesis_invalidations": report.get("thesis_invalidations") or report.get("bear_case"),
        "biggest_risks": report.get("biggest_risks"),
        "blind_spots": report.get("blind_spots"),
        "evidence_quality": report.get("evidence_quality"),
        "missing_evidence": report.get("missing_evidence"),
        "confidence_breakdown": report.get("confidence_breakdown"),
        "full_report": report,
    }
    item.ai_state = dict(item.ai_state or {})
    item.ai_state.update({
        "ai_confidence": confidence,
        "ai_sentiment": report.get("sentiment"),
        "independent_action": report.get("independent_action"),
        "conviction": report.get("conviction"),
        "risk_level": report.get("risk_level"),
        "final_rating": report.get("final_rating"),
        "ai_report_generated_at": timestamp,
    })

    if previous_confidence is not None and confidence is not None and float(previous_confidence) != confidence:
        item.timeline.append({
            "timestamp": utc_now(),
            "event": "AI Confidence changed",
            "details": f"{previous_confidence} → {confidence}",
        })

    already_saved = any(
        snap.get("source") == "independent_ai" and snap.get("report_timestamp") == timestamp
        for snap in item.research_snapshots
    )
    if not already_saved:
        item.research_snapshots.append({
            "timestamp": utc_now(),
            "report_timestamp": timestamp,
            "source": "independent_ai",
            "title": "Full Independent AI Research",
            "content": report.get("executive_summary") or "Independent AI research completed.",
            "ai_confidence": confidence,
            "report": report,
        })
        item.timeline.append({
            "timestamp": utc_now(),
            "event": "Independent AI research saved",
            "details": f"AI Confidence: {confidence if confidence is not None else 'unavailable'}",
        })
    return True


def refresh_item_from_scan(
    item: WatchlistItem,
    row: Dict[str, Any],
    ai_report: Dict[str, Any] | None = None,
    market_context: Dict[str, Any] | None = None,
    news_context: Any = None,
    smart_money_context: Dict[str, Any] | None = None,
    trade_intelligence_context: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    previous = dict(item.ai_state or {})
    events: List[Dict[str, Any]] = []

    if ai_report:
        sync_ai_report_to_item(item, ai_report)
    ai_confidence = _number((item.ai_state or {}).get("ai_confidence"))
    opportunity, reason, components = calculate_opportunity_score(row, ai_confidence=ai_confidence)
    grade = _pick(row, "Grade", default="—")
    setup = _pick(row, "Setup", default="—")

    profile = get_company_profile(item.symbol)
    item.company = str(_pick(row, "Company", "Name", default=item.company or profile.get("company")) or "")
    item.sector = str(_pick(row, "Sector", default=item.sector or profile.get("sector")) or "")
    item.industry = str(_pick(row, "Industry", default=item.industry or profile.get("industry")) or "")

    item.technical = {
        "price": _pick(row, "Price", "Close"),
        "grade": grade,
        "momo_score": _pick(row, "Momo Score"),
        "momo_confidence": _pick(row, "Momo Confidence"),
        "dee_fit": _pick(row, "Dee Fit"),
        "setup": setup,
        "relative_strength": _pick(row, "Relative Strength", "RS Score"),
        "distance_ema21_pct": _pick(row, "Distance EMA21 %"),
        "ema21": _pick(row, "EMA21", "EMA 21"),
        "ema50": _pick(row, "EMA50", "EMA 50"),
        "ema200": _pick(row, "EMA200", "EMA 200"),
        "rsi": _pick(row, "RSI"),
        "macd": _pick(row, "MACD"),
        "rvol": _pick(row, "RVOL"),
        "atr_pct": _pick(row, "ATR %", "ATR%"),
        "reference_entry": _pick(row, "Reference Entry"),
        "risk_reference": _pick(row, "Risk Reference"),
        "reward_reference": _pick(row, "Reward Reference"),
        "risk_reward": _pick(row, "Risk Reward", "T1 R"),
        "t1": _pick(row, "T1"),
        "t2": _pick(row, "T2"),
        "t3": _pick(row, "T3"),
        "t1_r": _pick(row, "T1 R"),
        "t2_r": _pick(row, "T2 R"),
        "t3_r": _pick(row, "T3 R"),
        "confidence_breakdown": _pick(row, "Confidence Breakdown"),
        "scanner_reasons": _pick(row, "Reasons"),
    }

    independent_ai = (item.intelligence or {}).get("independent_ai", {})
    item.intelligence = {
        **dict(item.intelligence or {}),
        "company_profile": profile,
        "market_context": market_context if market_context is not None else _pick(row, "Market Context"),
        "news_context": news_context if news_context is not None else _pick(row, "News Summary"),
        "smart_money": smart_money_context if smart_money_context is not None else _pick(row, "Smart Money"),
        "trading_intelligence": trade_intelligence_context if trade_intelligence_context is not None else _pick(row, "Trading Intelligence"),
        "independent_ai": independent_ai or {"status": "Not generated"},
    }

    status = "Thesis untested"
    thesis_lower = item.thesis.lower().strip()
    setup_lower = str(setup).lower()
    action_lower = str((item.ai_state or {}).get("independent_action") or "").lower()
    if thesis_lower:
        if any(x in action_lower for x in ("avoid", "sell")) or opportunity < 35:
            status = "Thesis weakening"
        elif "ema21" in thesis_lower and any(word in setup_lower for word in ("reclaim", "retest")):
            status = "Thesis strengthening"
        elif opportunity >= 75 or any(x in action_lower for x in ("buy", "enter")):
            status = "Thesis strengthening"
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
        **dict(item.ai_state or {}),
        "opportunity_score": opportunity,
        "opportunity_reason": reason,
        "opportunity_components": components,
        "thesis_status": status,
        "recommendation": recommendation,
        "grade": grade,
        "setup": setup,
        "last_updated": utc_now(),
    }

    comparisons = [
        ("Opportunity Score", previous.get("opportunity_score"), opportunity),
        ("Grade", previous.get("grade"), grade),
        ("Setup", previous.get("setup"), setup),
        ("Thesis Status", previous.get("thesis_status"), status),
        ("Recommendation", previous.get("recommendation"), recommendation),
    ]
    for label, old, new in comparisons:
        if old is not None and new is not None and str(old) != str(new):
            events.append({"timestamp": utc_now(), "event": f"{label} changed", "details": f"{old} → {new}"})
    item.timeline.extend(events)
    return events


def build_morning_brief(items: List[WatchlistItem]) -> Dict[str, Any]:
    ranked = sorted(items, key=lambda item: item.ai_state.get("opportunity_score", 0) or 0, reverse=True)
    improved = sum(1 for item in items if "strengthening" in str(item.ai_state.get("thesis_status", "")).lower())
    weakened = sum(1 for item in items if any(x in str(item.ai_state.get("thesis_status", "")).lower() for x in ("weakening", "invalid")))
    top = ranked[0] if ranked else None
    return {
        "count": len(items),
        "improved": improved,
        "weakened": weakened,
        "top_symbol": top.symbol if top else None,
        "top_opportunity": top.ai_state.get("opportunity_score") if top else None,
        "top_confidence": top.ai_state.get("ai_confidence") if top else None,
        "ranked": ranked,
    }

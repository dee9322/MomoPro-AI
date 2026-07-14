from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import quote


def _analysis_payload(analysis: Any) -> dict[str, Any]:
    if analysis is None:
        return {}
    if hasattr(analysis, "to_dict"):
        return analysis.to_dict()
    return dict(analysis or {})


def build_tradingview_payload(analysis: Any, timeframe: str = "1D") -> dict[str, Any]:
    data = _analysis_payload(analysis)
    plan = dict(data.get("plan") or {})
    symbol = str(data.get("symbol") or "").upper().strip()
    generated_at = str(data.get("generated_at") or datetime.now(timezone.utc).isoformat())
    trade_id_source = f"{symbol}|{generated_at}|{plan.get('reference_entry')}|{plan.get('stop')}"
    trade_id = hashlib.sha256(trade_id_source.encode("utf-8")).hexdigest()[:16]
    return {
        "schema": "momopro.tradingview.plan.v1",
        "trade_id": trade_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "generated_at": generated_at,
        "setup": data.get("setup"),
        "grade": data.get("grade"),
        "momo_score": data.get("momo_score"),
        "momo_confidence": data.get("momo_confidence"),
        "opportunity_score": data.get("opportunity_score"),
        "ai_confidence": data.get("ai_confidence"),
        "ai_action": data.get("ai_action"),
        "thesis": data.get("thesis"),
        "invalidation": data.get("invalidation"),
        "entry_low": plan.get("entry_low"),
        "entry_high": plan.get("entry_high"),
        "reference_entry": plan.get("reference_entry"),
        "stop": plan.get("stop"),
        "t1": plan.get("t1"),
        "t2": plan.get("t2"),
        "t3": plan.get("t3"),
        "support": plan.get("support"),
        "resistance": plan.get("resistance"),
        "risk_reward": plan.get("risk_reward"),
        "source": plan.get("source") or "MomoPro Canonical Engine",
    }


def payload_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload or {}), indent=2, default=str)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _number(value: Any) -> str:
    if value in (None, ""):
        return "0.0"
    try:
        return str(round(float(value), 4))
    except (TypeError, ValueError):
        return "0.0"


def _packet_text(value: Any) -> str:
    return _text(value).replace("|", "/").replace("\n", " ").strip()


def official_plan_packet(payload: Mapping[str, Any]) -> str:
    """Return the compact pipe-delimited packet used by the Pine hotfix."""
    p = dict(payload or {})
    fields = [
        _packet_text(p.get("trade_id")),
        _packet_text(p.get("symbol")),
        _packet_text(p.get("timeframe") or "1D"),
        _packet_text(p.get("setup")),
        _packet_text(p.get("grade")),
        _number(p.get("entry_low")),
        _number(p.get("entry_high")),
        _number(p.get("stop")),
        _number(p.get("t1")),
        _number(p.get("t2")),
        _number(p.get("t3")),
        _number(p.get("support")),
        _number(p.get("resistance")),
        _number(p.get("momo_score")),
        _number(p.get("opportunity_score")),
        _number(p.get("ai_confidence")),
    ]
    return "|".join(fields)


def pine_input_block(payload: Mapping[str, Any]) -> str:
    """Return the compact Linked Plan packet that avoids Pine's main-body limit."""
    return "\n".join(
        [
            "MOMOPRO AI LINKED PLAN — COPY INTO INDICATOR SETTINGS",
            "Enable Linked Plan Mode: ON",
            f"Official Plan Packet: {official_plan_packet(payload)}",
            "Show Official Entry / Stop / Targets: ON",
            "Show Official Support / Resistance: ON",
            "Show Official Plan Panel: ON",
        ]
    )


def tradingview_chart_url(symbol: str, timeframe: str = "1D") -> str:
    interval_map = {"1D": "D", "4H": "240", "1H": "60", "15m": "15", "5m": "5"}
    interval = interval_map.get(timeframe, "D")
    return f"https://www.tradingview.com/chart/?symbol={quote(str(symbol).upper().strip())}&interval={interval}"

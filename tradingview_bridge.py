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


def pine_input_block(payload: Mapping[str, Any]) -> str:
    p = dict(payload or {})
    def value(key: str) -> str:
        item = p.get(key)
        return "na" if item in (None, "") else str(item)
    return "\n".join([
        "MOMOPRO LINKED PLAN",
        f"Trade ID: {value('trade_id')}",
        f"Symbol: {value('symbol')}",
        f"Timeframe: {value('timeframe')}",
        f"Entry Low: {value('entry_low')}",
        f"Entry High: {value('entry_high')}",
        f"Stop: {value('stop')}",
        f"T1: {value('t1')}",
        f"T2: {value('t2')}",
        f"T3: {value('t3')}",
        f"Support: {value('support')}",
        f"Resistance: {value('resistance')}",
        f"Setup: {value('setup')}",
        f"Grade: {value('grade')}",
        f"Momo Score: {value('momo_score')}",
        f"Opportunity Score: {value('opportunity_score')}",
        f"AI Confidence: {value('ai_confidence')}",
    ])


def tradingview_chart_url(symbol: str, timeframe: str = "1D") -> str:
    interval_map = {"1D": "D", "4H": "240", "1H": "60", "15m": "15", "5m": "5"}
    interval = interval_map.get(timeframe, "D")
    return f"https://www.tradingview.com/chart/?symbol={quote(str(symbol).upper().strip())}&interval={interval}"

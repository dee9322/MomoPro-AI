from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CanonicalTradePlan:
    entry_low: float | None = None
    entry_high: float | None = None
    reference_entry: float | None = None
    stop: float | None = None
    t1: float | None = None
    t2: float | None = None
    t3: float | None = None
    support: float | None = None
    resistance: float | None = None
    risk_reward: float | None = None
    t1_r: float | None = None
    t2_r: float | None = None
    t3_r: float | None = None
    source: str = "MomoPro Canonical Engine"


@dataclass
class MomoAnalysis:
    symbol: str
    generated_at: str = field(default_factory=utc_now_iso)
    schema_version: str = "0.95A"
    data_freshness: dict[str, Any] = field(default_factory=dict)
    identity: dict[str, Any] = field(default_factory=dict)
    technicals: dict[str, Any] = field(default_factory=dict)
    market_context: dict[str, Any] = field(default_factory=dict)
    news_context: dict[str, Any] = field(default_factory=dict)
    smart_money_context: dict[str, Any] = field(default_factory=dict)
    trading_intelligence: dict[str, Any] = field(default_factory=dict)
    ai_research: dict[str, Any] = field(default_factory=dict)
    learning_context: dict[str, Any] = field(default_factory=dict)
    setup: str = ""
    grade: str = ""
    momo_score: float | None = None
    momo_confidence: float | None = None
    opportunity_score: float | None = None
    ai_confidence: float | None = None
    ai_action: str = ""
    thesis: str = ""
    invalidation: str = ""
    plan: CanonicalTradePlan = field(default_factory=CanonicalTradePlan)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MomoAnalysis":
        data = dict(payload or {})
        data["plan"] = CanonicalTradePlan(**(data.get("plan") or {}))
        return cls(**data)

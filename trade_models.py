from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class TradeExit:
    id: str = field(default_factory=lambda: uuid4().hex)
    date: str = field(default_factory=utc_now)
    shares: float = 0.0
    price: float = 0.0
    reason: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TradeExit":
        allowed = {name for name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in (data or {}).items() if key in allowed})


@dataclass
class TradeUpdate:
    id: str = field(default_factory=lambda: uuid4().hex)
    date: str = field(default_factory=utc_now)
    update_type: str = "Management Note"
    note: str = ""
    stop: float | None = None
    current_price: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TradeUpdate":
        allowed = {name for name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in (data or {}).items() if key in allowed})


@dataclass
class TradeRecord:
    id: str = field(default_factory=lambda: uuid4().hex)
    symbol: str = ""
    status: str = "open"
    direction: str = "long"
    entry_date: str = field(default_factory=utc_now)
    entry_price: float = 0.0
    shares: float = 0.0
    initial_stop: float | None = None
    current_stop: float | None = None
    t1: float | None = None
    t2: float | None = None
    t3: float | None = None
    setup: str = ""
    grade: str = ""
    momo_score: float | None = None
    momo_confidence: float | None = None
    dee_fit: str = ""
    opportunity_score: float | None = None
    ai_confidence: float | None = None
    ai_action: str = ""
    market_regime: str = ""
    sector_context: str = ""
    news_context: str = ""
    smart_money_context: str = ""
    thesis: str = ""
    confirmation: str = ""
    invalidation: str = ""
    notes: str = ""
    screenshot_paths: list[str] = field(default_factory=list)
    exits: list[TradeExit] = field(default_factory=list)
    updates: list[TradeUpdate] = field(default_factory=list)
    exit_date: str | None = None
    exit_reason: str = ""
    planned_exit_followed: str = "Not Reviewed"
    rule_following_score: float | None = None
    mistakes: str = ""
    strengths: str = ""
    lessons: str = ""
    ai_review: str = ""
    source: str = "manual"
    broker: str = ""
    broker_execution_ids: list[str] = field(default_factory=list)
    broker_fees: float = 0.0
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @property
    def exited_shares(self) -> float:
        return round(sum(max(float(exit.shares or 0), 0.0) for exit in self.exits), 8)

    @property
    def remaining_shares(self) -> float:
        return max(round(float(self.shares or 0) - self.exited_shares, 8), 0.0)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["exits"] = [asdict(item) for item in self.exits]
        payload["updates"] = [asdict(item) for item in self.updates]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TradeRecord":
        payload = dict(data or {})
        payload["exits"] = [TradeExit.from_dict(item) for item in payload.get("exits", []) if isinstance(item, dict)]
        payload["updates"] = [TradeUpdate.from_dict(item) for item in payload.get("updates", []) if isinstance(item, dict)]
        allowed = {name for name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in payload.items() if key in allowed})

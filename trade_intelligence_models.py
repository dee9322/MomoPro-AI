from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from trade_models import utc_now


@dataclass
class TradeEvidence:
    id: str = field(default_factory=lambda: uuid4().hex)
    evidence_type: str = ""
    label: str = ""
    source: str = ""
    observed_at: str = field(default_factory=utc_now)
    confidence: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TradeEvidence":
        allowed = set(cls.__dataclass_fields__)
        return cls(
            **{
                key: value
                for key, value in (data or {}).items()
                if key in allowed
            }
        )


@dataclass
class TradeTimelineEvent:
    id: str = field(default_factory=lambda: uuid4().hex)
    event_at: str = field(default_factory=utc_now)
    event_type: str = ""
    title: str = ""
    description: str = ""
    source: str = ""
    confidence: float = 100.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any] | None,
    ) -> "TradeTimelineEvent":
        allowed = set(cls.__dataclass_fields__)
        return cls(
            **{
                key: value
                for key, value in (data or {}).items()
                if key in allowed
            }
        )

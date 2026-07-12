from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WatchlistItem:
    symbol: str
    company: str = ""
    sector: str = ""
    industry: str = ""
    thesis: str = ""
    entry_idea: str = ""
    stop: float | None = None
    target: float | None = None
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    technical: Dict[str, Any] = field(default_factory=dict)
    intelligence: Dict[str, Any] = field(default_factory=dict)
    ai_state: Dict[str, Any] = field(default_factory=dict)
    alert_rule_ids: List[str] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    research_snapshots: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WatchlistItem":
        allowed = cls.__dataclass_fields__.keys()
        clean = {key: value for key, value in dict(data or {}).items() if key in allowed}
        clean.setdefault("symbol", "")
        return cls(**clean)

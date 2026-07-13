from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_execution_id(*parts: Any) -> str:
    raw = "|".join(str(part or "").strip() for part in parts)
    return sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class BrokerExecution:
    id: str = field(default_factory=lambda: uuid4().hex)
    fingerprint: str = ""
    broker: str = "Webull"
    account_id: str = ""
    order_id: str = ""
    execution_id: str = ""
    symbol: str = ""
    side: str = "BUY"
    quantity: float = 0.0
    price: float = 0.0
    executed_at: str = field(default_factory=utc_now)
    fees: float = 0.0
    currency: str = "USD"
    status: str = "Filled"
    source_file: str = ""
    import_id: str = ""
    matched_trade_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BrokerExecution":
        allowed = {name for name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in (data or {}).items() if key in allowed})


@dataclass
class BrokerImportRecord:
    id: str = field(default_factory=lambda: uuid4().hex)
    broker: str = "Webull"
    source_file: str = ""
    imported_at: str = field(default_factory=utc_now)
    rows_seen: int = 0
    rows_imported: int = 0
    duplicates_skipped: int = 0
    rows_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BrokerImportRecord":
        allowed = {name for name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in (data or {}).items() if key in allowed})

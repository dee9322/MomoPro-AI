from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trade_models import TradeRecord, utc_now

TRADE_DATA_FILE = Path(__file__).with_name("trade_data.json")
ATTACHMENT_DIR = Path(__file__).with_name("journal_attachments")
DEFAULT_PAYLOAD = {"schema_version": 1, "updated_at": None, "trades": []}


def _ensure_storage() -> None:
    if not TRADE_DATA_FILE.exists():
        save_payload(DEFAULT_PAYLOAD)


def load_payload() -> dict[str, Any]:
    _ensure_storage()
    try:
        payload = json.loads(TRADE_DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_PAYLOAD)
    if not isinstance(payload, dict):
        return dict(DEFAULT_PAYLOAD)
    payload.setdefault("schema_version", 1)
    payload.setdefault("trades", [])
    return payload


def save_payload(payload: dict[str, Any]) -> None:
    TRADE_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    clean = dict(payload)
    clean["updated_at"] = utc_now()
    temp = TRADE_DATA_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(TRADE_DATA_FILE)


def load_trades() -> list[TradeRecord]:
    return [TradeRecord.from_dict(item) for item in load_payload().get("trades", []) if isinstance(item, dict)]


def save_trades(trades: list[TradeRecord]) -> None:
    payload = load_payload()
    payload["trades"] = [trade.to_dict() for trade in trades]
    save_payload(payload)


def save_attachment(trade_id: str, uploaded_file) -> str | None:
    if uploaded_file is None:
        return None
    safe_name = Path(uploaded_file.name).name.replace(" ", "_")
    ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
    destination = ATTACHMENT_DIR / f"{trade_id}_{safe_name}"
    destination.write_bytes(uploaded_file.getbuffer())
    return str(destination.relative_to(Path(__file__).parent))

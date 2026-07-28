from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from cloud_storage import cloud_available, load_document, save_document
from integration_models import IntegrationConnection

DATA_PATH = Path(__file__).with_name("integration_data.json")
BUCKET = "integrations"
DEFAULT = {"schema_version": "0.95A", "connections": {}, "events": []}


def _load_local() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return dict(DEFAULT)
    try:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT)
    return payload if isinstance(payload, dict) else dict(DEFAULT)


def load_integrations() -> dict[str, Any]:
    local = _load_local()
    payload = load_document(BUCKET, local) if cloud_available() else local
    if not isinstance(payload, dict):
        payload = dict(DEFAULT)
    payload.setdefault("schema_version", "0.95A")
    payload.setdefault("connections", {})
    payload.setdefault("events", [])
    return payload


def _save(payload: dict[str, Any]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="integration_", suffix=".json", dir=DATA_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        os.replace(name, DATA_PATH)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    if cloud_available():
        save_document(BUCKET, payload)


def save_connection(connection: IntegrationConnection) -> None:
    payload = load_integrations()
    payload["connections"][connection.integration] = connection.to_dict()
    _save(payload)


def get_connection(name: str) -> dict[str, Any] | None:
    return load_integrations().get("connections", {}).get(name)


def record_event(event: dict[str, Any], limit: int = 500) -> None:
    payload = load_integrations()
    events = list(payload.get("events") or [])
    events.insert(0, dict(event or {}))
    payload["events"] = events[: max(1, int(limit))]
    _save(payload)


def list_events(limit: int = 100, source: str | None = None) -> list[dict[str, Any]]:
    events = list(load_integrations().get("events") or [])
    if source:
        events = [event for event in events if event.get("source") == source]
    return events[: max(1, int(limit))]

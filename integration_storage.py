from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from integration_models import IntegrationConnection

DATA_PATH = Path(__file__).with_name("integration_data.json")


def load_integrations() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {"schema_version": "0.95A", "connections": {}, "events": []}
    try:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": "0.95A", "connections": {}, "events": []}
    payload.setdefault("schema_version", "0.95A")
    payload.setdefault("connections", {})
    payload.setdefault("events", [])
    return payload


def _save(payload: dict[str, Any]) -> None:
    fd, name = tempfile.mkstemp(prefix="integration_", suffix=".json", dir=DATA_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        os.replace(name, DATA_PATH)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save_connection(connection: IntegrationConnection) -> None:
    payload = load_integrations()
    payload["connections"][connection.integration] = connection.to_dict()
    _save(payload)


def get_connection(name: str) -> dict[str, Any] | None:
    return load_integrations().get("connections", {}).get(name)

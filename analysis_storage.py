from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from analysis_models import MomoAnalysis
from cloud_storage import cloud_available, load_document, save_document

DATA_PATH = Path(__file__).with_name("analysis_data.json")
BUCKET = "analyses"
DEFAULT = {"schema_version": "0.95A", "analyses": {}}


def _load_local() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return dict(DEFAULT)
    try:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT)
    return payload if isinstance(payload, dict) else dict(DEFAULT)


def _load_raw() -> dict[str, Any]:
    local = _load_local()
    payload = load_document(BUCKET, local) if cloud_available() else local
    if not isinstance(payload, dict):
        payload = dict(DEFAULT)
    payload.setdefault("schema_version", "0.95A")
    payload.setdefault("analyses", {})
    return payload


def _atomic_write(payload: dict[str, Any]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="analysis_", suffix=".json", dir=DATA_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        os.replace(temp_name, DATA_PATH)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    if cloud_available():
        save_document(BUCKET, payload)


def save_analysis(analysis: MomoAnalysis) -> None:
    payload = _load_raw()
    payload["analyses"][analysis.symbol] = analysis.to_dict()
    _atomic_write(payload)


def get_analysis(symbol: str) -> MomoAnalysis | None:
    raw = _load_raw().get("analyses", {}).get(str(symbol).upper().strip())
    return MomoAnalysis.from_dict(raw) if raw else None


def list_analyses() -> list[MomoAnalysis]:
    return [MomoAnalysis.from_dict(item) for item in _load_raw().get("analyses", {}).values()]


def delete_analysis(symbol: str) -> bool:
    payload = _load_raw()
    removed = payload.get("analyses", {}).pop(str(symbol).upper().strip(), None)
    if removed is not None:
        _atomic_write(payload)
        return True
    return False

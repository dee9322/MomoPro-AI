"""Persistent JSON storage for MomoPro AI settings."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from settings_models import DEFAULT_SETTINGS, merge_defaults

SETTINGS_PATH = Path(os.getenv("MOMOPRO_SETTINGS_PATH", "settings_data.json"))


def load_settings() -> Dict[str, Any]:
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return merge_defaults(DEFAULT_SETTINGS)
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = DEFAULT_SETTINGS
    merged = merge_defaults(payload)
    if merged != payload:
        save_settings(merged)
    return merged


def save_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    clean = merge_defaults(settings)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="momopro_settings_", suffix=".json", dir=str(SETTINGS_PATH.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(clean, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, SETTINGS_PATH)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return clean


def reset_settings() -> Dict[str, Any]:
    return save_settings(DEFAULT_SETTINGS)

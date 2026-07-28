from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cloud_storage import load_document, save_document

MIGRATION_BUCKET = "migration_state"

SOURCES = {
    "trade_data": "trade_data.json",
    "settings": "settings_data.json",
    "watchlists": "watchlist_data.json",
    "learning": "learning_data.json",
    "analyses": "analysis_data.json",
    "alerts": "alert_data.json",
    "integrations": "integration_data.json",
    "webull_snapshot": "webull_sync_data.json",
    "webull_order_detail_cache": "webull_order_detail_cache.json",
}


def migration_status() -> dict[str, Any]:
    value = load_document(MIGRATION_BUCKET, {"completed": False, "buckets": []})
    return value if isinstance(value, dict) else {"completed": False, "buckets": []}


def migrate_local_json_once(base_dir: str | Path | None = None) -> dict[str, Any]:
    status = migration_status()
    if status.get("completed"):
        return status
    root = Path(base_dir or Path(__file__).parent)
    migrated: list[str] = []
    skipped: list[str] = []
    for bucket, filename in SOURCES.items():
        existing = load_document(bucket, None)
        if existing not in (None, {}, []):
            skipped.append(bucket)
            continue
        path = root / filename
        if not path.exists():
            skipped.append(bucket)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped.append(bucket)
            continue
        if save_document(bucket, payload):
            migrated.append(bucket)
        else:
            skipped.append(bucket)
    result = {"completed": True, "buckets": migrated, "skipped": skipped}
    save_document(MIGRATION_BUCKET, result)
    return result

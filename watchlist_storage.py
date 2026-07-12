from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any, Dict

from watchlist_models import WatchlistItem, utc_now

DATA_PATH = Path(os.getenv("MOMOPRO_WATCHLIST_PATH", "watchlist_data.json"))
_LOCK = RLock()
DEFAULT_DATA = {"schema_version": 1, "watchlists": {"Main Watchlist": []}, "items": {}}


def _atomic_write(data: Dict[str, Any]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=DATA_PATH.name, suffix=".tmp", dir=str(DATA_PATH.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        os.replace(tmp_name, DATA_PATH)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def load_data() -> Dict[str, Any]:
    with _LOCK:
        if not DATA_PATH.exists():
            _atomic_write(DEFAULT_DATA)
        try:
            with DATA_PATH.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            data = json.loads(json.dumps(DEFAULT_DATA))
            _atomic_write(data)
        data.setdefault("schema_version", 1)
        data.setdefault("watchlists", {"Main Watchlist": []})
        data.setdefault("items", {})
        if not data["watchlists"]:
            data["watchlists"] = {"Main Watchlist": []}
        return data


def save_data(data: Dict[str, Any]) -> None:
    with _LOCK:
        _atomic_write(data)


def get_item(data: Dict[str, Any], symbol: str) -> WatchlistItem | None:
    raw = data.get("items", {}).get(symbol.upper())
    return WatchlistItem.from_dict(raw) if raw else None


def put_item(data: Dict[str, Any], item: WatchlistItem) -> None:
    item.symbol = item.symbol.upper().strip()
    item.updated_at = utc_now()
    data.setdefault("items", {})[item.symbol] = item.to_dict()

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_PATH = Path(__file__).with_name("learning_data.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default() -> dict[str, Any]:
    return {"version": 1, "snapshots": [], "approved_rules": [], "updated_at": _now()}


def load_learning_data(path: str | Path = DEFAULT_PATH) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        save_learning_data(_default(), target)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = _default()
    base = _default()
    base.update(payload if isinstance(payload, dict) else {})
    base["snapshots"] = base.get("snapshots") if isinstance(base.get("snapshots"), list) else []
    base["approved_rules"] = base.get("approved_rules") if isinstance(base.get("approved_rules"), list) else []
    return base


def save_learning_data(data: dict[str, Any], path: str | Path = DEFAULT_PATH) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data or {})
    payload["updated_at"] = _now()
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, target)


def save_snapshot(summary: dict[str, Any], path: str | Path = DEFAULT_PATH) -> dict[str, Any]:
    data = load_learning_data(path)
    snapshot = {"id": uuid4().hex, "created_at": _now(), **dict(summary or {})}
    data["snapshots"].append(snapshot)
    data["snapshots"] = data["snapshots"][-100:]
    save_learning_data(data, path)
    return snapshot


def add_approved_rule(rule: str, rationale: str = "", path: str | Path = DEFAULT_PATH) -> dict[str, Any]:
    text = str(rule or "").strip()
    if not text:
        raise ValueError("Rule cannot be blank.")
    data = load_learning_data(path)
    item = {"id": uuid4().hex, "rule": text, "rationale": str(rationale or "").strip(), "created_at": _now(), "enabled": True}
    data["approved_rules"].append(item)
    save_learning_data(data, path)
    return item


def set_rule_enabled(rule_id: str, enabled: bool, path: str | Path = DEFAULT_PATH) -> bool:
    data = load_learning_data(path)
    changed = False
    for item in data["approved_rules"]:
        if item.get("id") == rule_id:
            item["enabled"] = bool(enabled)
            changed = True
            break
    if changed:
        save_learning_data(data, path)
    return changed


def delete_rule(rule_id: str, path: str | Path = DEFAULT_PATH) -> bool:
    data = load_learning_data(path)
    before = len(data["approved_rules"])
    data["approved_rules"] = [item for item in data["approved_rules"] if item.get("id") != rule_id]
    changed = len(data["approved_rules"]) != before
    if changed:
        save_learning_data(data, path)
    return changed

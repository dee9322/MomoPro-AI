from __future__ import annotations

"""v0.98.3 application initialization and automatic data-loading manager.

This module gives every page the same lifecycle:
1. restore the last saved result immediately;
2. decide whether it is fresh using the user's cache preference;
3. refresh stale/missing content automatically;
4. keep an explicit force-refresh control;
5. expose freshness and load-state information consistently.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd
import streamlit as st

from cloud_storage import load_document, save_document

BUCKET = "automatic_data_cache_v0983"
STATE_KEY = "momopro_automatic_data_cache"
STATUS_KEY = "momopro_automatic_loading_status"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _serialize(value: Any) -> dict[str, Any]:
    if isinstance(value, pd.DataFrame):
        return {"kind": "dataframe", "value": value.to_dict(orient="records")}
    if isinstance(value, (dict, list, tuple, str, int, float, bool)) or value is None:
        return {"kind": "json", "value": value}
    return {"kind": "json", "value": None}


def _deserialize(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return None
    if payload.get("kind") == "dataframe":
        try:
            return pd.DataFrame(payload.get("value") or [])
        except Exception:
            return pd.DataFrame()
    return payload.get("value")


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, pd.DataFrame):
        return not value.empty
    if isinstance(value, (dict, list, tuple, set)):
        return bool(value)
    return True


def initialize_automatic_loading() -> dict[str, Any]:
    """Restore persisted page data once, before page-specific loaders run."""
    if STATE_KEY not in st.session_state:
        stored = load_document(BUCKET, {})
        st.session_state[STATE_KEY] = stored if isinstance(stored, dict) else {}
    st.session_state.setdefault(STATUS_KEY, {})
    return st.session_state[STATE_KEY]


def restore_saved_resource(resource: str, state_key: str) -> Any:
    cache = initialize_automatic_loading()
    current = st.session_state.get(state_key)
    if _has_value(current):
        return current
    entry = cache.get(resource) if isinstance(cache, dict) else None
    if isinstance(entry, dict):
        restored = _deserialize(entry.get("payload"))
        if _has_value(restored):
            st.session_state[state_key] = restored
            return restored
    return current


def resource_updated_at(resource: str) -> datetime | None:
    cache = initialize_automatic_loading()
    entry = cache.get(resource) if isinstance(cache, dict) else None
    return _parse_time(entry.get("updated_at")) if isinstance(entry, dict) else None


def resource_is_stale(resource: str, ttl_minutes: int) -> bool:
    updated = resource_updated_at(resource)
    if updated is None:
        return True
    age = (datetime.now(timezone.utc) - updated).total_seconds()
    return age >= max(1, int(ttl_minutes)) * 60


def _save_resource(resource: str, value: Any) -> None:
    cache = initialize_automatic_loading()
    cache[resource] = {"updated_at": _now(), "payload": _serialize(value)}
    st.session_state[STATE_KEY] = cache
    # Data persistence is useful, but a cloud outage must never block rendering.
    save_document(BUCKET, cache)


def _skeleton(label: str):
    box = st.empty()
    box.markdown(
        f"""
        <div style="border:1px solid rgba(128,128,128,.22);border-radius:12px;padding:16px;margin:.25rem 0 1rem 0;">
          <div style="font-weight:650;margin-bottom:10px;">{label}</div>
          <div style="height:12px;border-radius:8px;background:rgba(128,128,128,.18);margin:8px 0;"></div>
          <div style="height:12px;width:82%;border-radius:8px;background:rgba(128,128,128,.14);margin:8px 0;"></div>
          <div style="height:12px;width:64%;border-radius:8px;background:rgba(128,128,128,.10);margin:8px 0;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return box


def load_resource(
    resource: str,
    state_key: str,
    loader: Callable[[], Any],
    *,
    ttl_minutes: int,
    loading_label: str,
    force: bool = False,
) -> Any:
    """Show saved data first and automatically refresh only when stale/missing."""
    restored = restore_saved_resource(resource, state_key)
    stale = resource_is_stale(resource, ttl_minutes)
    if _has_value(restored) and not stale and not force:
        return restored

    lock_key = f"_automatic_load_in_progress::{resource}"
    if st.session_state.get(lock_key):
        return restored

    st.session_state[lock_key] = True
    placeholder = _skeleton(loading_label)
    try:
        value = loader()
        if _has_value(value):
            st.session_state[state_key] = value
            _save_resource(resource, value)
            st.session_state[STATUS_KEY][resource] = {"status": "loaded", "updated_at": _now()}
            return value
        st.session_state[STATUS_KEY][resource] = {"status": "empty", "updated_at": _now()}
        return restored
    except Exception as error:
        st.session_state[STATUS_KEY][resource] = {
            "status": "error", "error": str(error), "updated_at": _now()
        }
        if not _has_value(restored):
            st.warning(f"{loading_label} could not complete: {error}")
        return restored
    finally:
        placeholder.empty()
        st.session_state[lock_key] = False


def force_refresh_resource(resource: str, state_key: str, loader: Callable[[], Any], *, ttl_minutes: int, loading_label: str) -> Any:
    return load_resource(
        resource, state_key, loader,
        ttl_minutes=ttl_minutes,
        loading_label=loading_label,
        force=True,
    )


def freshness_text(resource: str) -> str:
    updated = resource_updated_at(resource)
    if updated is None:
        return "Never updated"
    seconds = max(0, int((datetime.now(timezone.utc) - updated).total_seconds()))
    if seconds < 60:
        return "Updated just now"
    if seconds < 3600:
        return f"Updated {seconds // 60} min ago"
    if seconds < 86400:
        return f"Updated {seconds // 3600} hr ago"
    return f"Updated {updated.astimezone().strftime('%b %-d, %-I:%M %p')}"


def render_freshness(resource: str, *, ttl_minutes: int, label: str = "Data") -> None:
    stale = resource_is_stale(resource, ttl_minutes)
    status = "stale — refreshing automatically" if stale else "fresh"
    st.caption(f"{label}: {freshness_text(resource)} · {status} · refresh window {int(ttl_minutes)} min")

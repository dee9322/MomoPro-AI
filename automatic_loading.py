from __future__ import annotations

"""Non-blocking v0.98.3 page-data lifecycle for Streamlit.

The full app run only queues work. A timed Streamlit fragment performs cloud
restore and live refresh after the page shell has painted, then reruns the app.
Each resource is persisted in its own document so opening one page never
retrieves unrelated scanner/news/market payloads.
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Callable

import pandas as pd
import streamlit as st

from cloud_storage import load_document, save_document

LEGACY_BUCKET = "automatic_data_cache_v0983"
STATE_KEY = "momopro_automatic_data_cache"
STATUS_KEY = "momopro_automatic_loading_status"
QUEUE_KEY = "momopro_automatic_loading_queue"
JOBS_KEY = "momopro_automatic_loading_jobs"
ARMED_KEY = "momopro_automatic_loader_armed"
LEGACY_KEY = "momopro_automatic_legacy_cache"


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


def _bucket(resource: str) -> str:
    digest = hashlib.sha1(resource.encode("utf-8")).hexdigest()[:16]
    return f"automatic_resource_v0983_{digest}"


def initialize_automatic_loading() -> dict[str, Any]:
    """Initialize in-memory state only. Never perform network I/O here."""
    st.session_state.setdefault(STATE_KEY, {})
    st.session_state.setdefault(STATUS_KEY, {})
    st.session_state.setdefault(QUEUE_KEY, [])
    st.session_state.setdefault(JOBS_KEY, {})
    return st.session_state[STATE_KEY]


def restore_saved_resource(resource: str, state_key: str) -> Any:
    """Return session data only; cloud restoration is queued by load_resource."""
    initialize_automatic_loading()
    return st.session_state.get(state_key)


def resource_updated_at(resource: str) -> datetime | None:
    initialize_automatic_loading()
    entry = st.session_state[STATE_KEY].get(resource) or {}
    return _parse_time(entry.get("updated_at"))


def resource_is_stale(resource: str, ttl_minutes: int) -> bool:
    updated = resource_updated_at(resource)
    if updated is None:
        return True
    return (datetime.now(timezone.utc) - updated).total_seconds() >= max(1, int(ttl_minutes)) * 60


def _queue_job(
    resource: str,
    state_key: str,
    loader: Callable[[], Any],
    ttl_minutes: int,
    loading_label: str,
    force: bool,
) -> None:
    initialize_automatic_loading()
    jobs = st.session_state[JOBS_KEY]
    queued = st.session_state[QUEUE_KEY]
    jobs[resource] = {
        "resource": resource,
        "state_key": state_key,
        "loader": loader,
        "ttl_minutes": int(ttl_minutes),
        "loading_label": loading_label,
        "force": bool(force or (jobs.get(resource) or {}).get("force")),
    }
    if resource not in queued:
        queued.append(resource)
    st.session_state[STATUS_KEY][resource] = {
        "status": "queued",
        "updated_at": _now(),
        "label": loading_label,
    }


def load_resource(
    resource: str,
    state_key: str,
    loader: Callable[[], Any],
    *,
    ttl_minutes: int,
    loading_label: str,
    force: bool = False,
) -> Any:
    """Return available data immediately and queue restore/refresh after paint."""
    initialize_automatic_loading()
    current = st.session_state.get(state_key)
    if force or not _has_value(current) or resource_is_stale(resource, ttl_minutes):
        _queue_job(resource, state_key, loader, ttl_minutes, loading_label, force)
    return current


def force_refresh_resource(resource: str, state_key: str, loader: Callable[[], Any], *, ttl_minutes: int, loading_label: str) -> Any:
    return load_resource(
        resource, state_key, loader,
        ttl_minutes=ttl_minutes,
        loading_label=loading_label,
        force=True,
    )


def _legacy_entry(resource: str) -> dict[str, Any] | None:
    if LEGACY_KEY not in st.session_state:
        stored = load_document(LEGACY_BUCKET, {})
        st.session_state[LEGACY_KEY] = stored if isinstance(stored, dict) else {}
    entry = st.session_state[LEGACY_KEY].get(resource)
    return entry if isinstance(entry, dict) else None


def _restore_entry(resource: str) -> dict[str, Any] | None:
    stored = load_document(_bucket(resource), {})
    if isinstance(stored, dict) and stored.get("payload"):
        return stored
    return _legacy_entry(resource)


@st.fragment(run_every=0.75)
def render_automatic_loading_worker() -> None:
    """Process one queued resource outside the full app render."""
    initialize_automatic_loading()

    # During the initial full-app execution, arm the worker and return so the
    # complete page shell paints before any cloud or provider request begins.
    if not st.session_state.get(ARMED_KEY):
        st.session_state[ARMED_KEY] = True
        return

    queue = st.session_state.get(QUEUE_KEY) or []
    if not queue:
        return

    resource = queue[0]
    job = (st.session_state.get(JOBS_KEY) or {}).get(resource)
    if not isinstance(job, dict):
        queue.pop(0)
        return

    state_key = job["state_key"]
    ttl_minutes = int(job["ttl_minutes"])
    force = bool(job.get("force"))
    label = str(job.get("loading_label") or "Loading data")
    status_box = st.empty()
    status_box.info(f"{label}…")

    try:
        current = st.session_state.get(state_key)
        entry = None
        if not force and not _has_value(current):
            entry = _restore_entry(resource)
            if isinstance(entry, dict):
                restored = _deserialize(entry.get("payload"))
                if _has_value(restored):
                    st.session_state[state_key] = restored
                    st.session_state[STATE_KEY][resource] = {
                        "updated_at": entry.get("updated_at"),
                    }
                    current = restored

        fresh = _has_value(current) and not resource_is_stale(resource, ttl_minutes)
        if not force and fresh:
            st.session_state[STATUS_KEY][resource] = {
                "status": "restored",
                "updated_at": _now(),
            }
        else:
            value = job["loader"]()
            if _has_value(value):
                updated_at = _now()
                st.session_state[state_key] = value
                st.session_state[STATE_KEY][resource] = {"updated_at": updated_at}
                st.session_state[STATUS_KEY][resource] = {
                    "status": "loaded",
                    "updated_at": updated_at,
                }
                # Separate persistence means scanner saves never rewrite news or market data.
                save_document(
                    _bucket(resource),
                    {"updated_at": updated_at, "payload": _serialize(value)},
                )
            else:
                st.session_state[STATUS_KEY][resource] = {
                    "status": "empty",
                    "updated_at": _now(),
                }
    except Exception as error:
        st.session_state[STATUS_KEY][resource] = {
            "status": "error",
            "error": str(error),
            "updated_at": _now(),
        }
    finally:
        if queue and queue[0] == resource:
            queue.pop(0)
        st.session_state[JOBS_KEY].pop(resource, None)
        status_box.empty()

    st.rerun(scope="app")


def freshness_text(resource: str) -> str:
    updated = resource_updated_at(resource)
    if updated is None:
        status = (st.session_state.get(STATUS_KEY) or {}).get(resource, {}).get("status")
        return "Loading automatically" if status in {"queued", "loading"} else "Not loaded yet"
    seconds = max(0, int((datetime.now(timezone.utc) - updated).total_seconds()))
    if seconds < 60:
        return "Updated just now"
    if seconds < 3600:
        return f"Updated {seconds // 60} min ago"
    if seconds < 86400:
        return f"Updated {seconds // 3600} hr ago"
    return f"Updated {updated.astimezone().strftime('%b %d, %I:%M %p')}"


def render_freshness(resource: str, *, ttl_minutes: int, label: str = "Data") -> None:
    status = (st.session_state.get(STATUS_KEY) or {}).get(resource, {}).get("status")
    if status == "error":
        st.caption(f"{label}: last refresh failed · use Refresh to retry")
        return
    stale = resource_is_stale(resource, ttl_minutes)
    state = "refresh queued" if status == "queued" else ("stale" if stale else "fresh")
    st.caption(f"{label}: {freshness_text(resource)} · {state} · refresh window {int(ttl_minutes)} min")

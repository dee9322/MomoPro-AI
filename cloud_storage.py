from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
from typing import Any

from supabase_backend import apply_access_token, get_supabase_client, is_supabase_configured
from user_context import current_user_id

TABLE = "user_documents"


def _session_access_token() -> str | None:
    """Return the active Supabase access token without coupling callers to auth state."""
    try:
        import streamlit as st

        auth = st.session_state.get("momopro_auth") or {}
        token = str(auth.get("access_token") or "").strip() if isinstance(auth, dict) else ""
        return token or None
    except Exception:
        return None



def _record_cloud_error(operation: str, bucket: str, error: Exception) -> None:
    try:
        import streamlit as st
        failures = dict(st.session_state.get("_momopro_cloud_errors") or {})
        failures[f"{operation}:{bucket}"] = str(error)
        st.session_state._momopro_cloud_errors = failures
    except Exception:
        pass


def verify_cloud_access(*, attempts: int = 3) -> tuple[bool, str]:
    """Verify authenticated Supabase access before durable state is loaded.

    A cold start must fail closed instead of silently replacing saved settings,
    plans, journal data, or broker state with repository defaults.
    """
    user_id = current_user_id()
    client = get_supabase_client()
    if not client or not user_id:
        return False, "Cloud user session is unavailable."
    last_error = ""
    for attempt in range(max(1, attempts)):
        try:
            apply_access_token(client, _session_access_token())
            client.table(TABLE).select("bucket").eq("user_id", user_id).limit(1).execute()
            return True, ""
        except Exception as error:
            last_error = str(error)
            if attempt + 1 < attempts:
                time.sleep(0.35 * (attempt + 1))
    _record_cloud_error("verify", "startup", RuntimeError(last_error))
    return False, last_error or "Unable to reach private cloud storage."

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cloud_available() -> bool:
    return bool(is_supabase_configured() and current_user_id())


def load_document(bucket: str, default: Any, *, access_token: str | None = None) -> Any:
    user_id = current_user_id()
    client = get_supabase_client()
    if not client or not user_id:
        return copy.deepcopy(default)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            apply_access_token(client, access_token or _session_access_token())
            response = (
                client.table(TABLE)
                .select("payload")
                .eq("user_id", user_id)
                .eq("bucket", str(bucket))
                .limit(1)
                .execute()
            )
            rows = response.data or []
            if rows and isinstance(rows[0], dict):
                payload = rows[0].get("payload")
                return copy.deepcopy(payload if payload is not None else default)
            return copy.deepcopy(default)
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(0.25 * (attempt + 1))
    if last_error is not None:
        _record_cloud_error("load", str(bucket), last_error)
    return copy.deepcopy(default)

def save_document(bucket: str, payload: Any, *, access_token: str | None = None) -> bool:
    user_id = current_user_id()
    client = get_supabase_client()
    if not client or not user_id:
        return False
    row = {
        "user_id": user_id,
        "bucket": str(bucket),
        "payload": payload,
        "updated_at": _now(),
    }
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            apply_access_token(client, access_token or _session_access_token())
            client.table(TABLE).upsert(row, on_conflict="user_id,bucket").execute()
            return True
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(0.25 * (attempt + 1))
    if last_error is not None:
        _record_cloud_error("save", str(bucket), last_error)
    return False

def delete_document(bucket: str, *, access_token: str | None = None) -> bool:
    user_id = current_user_id()
    client = get_supabase_client()
    if not client or not user_id:
        return False
    try:
        apply_access_token(client, access_token or _session_access_token())
        (
            client.table(TABLE)
            .delete()
            .eq("user_id", user_id)
            .eq("bucket", str(bucket))
            .execute()
        )
        return True
    except Exception:
        return False

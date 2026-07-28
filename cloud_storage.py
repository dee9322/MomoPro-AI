from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from supabase_backend import apply_access_token, get_supabase_client, is_supabase_configured
from user_context import current_user_id

TABLE = "user_documents"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cloud_available() -> bool:
    return bool(is_supabase_configured() and current_user_id())


def load_document(bucket: str, default: Any, *, access_token: str | None = None) -> Any:
    user_id = current_user_id()
    client = get_supabase_client()
    if not client or not user_id:
        return copy.deepcopy(default)
    try:
        apply_access_token(client, access_token)
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
    except Exception:
        pass
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
    try:
        apply_access_token(client, access_token)
        client.table(TABLE).upsert(row, on_conflict="user_id,bucket").execute()
        return True
    except Exception:
        return False


def delete_document(bucket: str, *, access_token: str | None = None) -> bool:
    user_id = current_user_id()
    client = get_supabase_client()
    if not client or not user_id:
        return False
    try:
        apply_access_token(client, access_token)
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

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import streamlit as st
from supabase import Client, create_client


def _secret(path: tuple[str, ...], default: str = "") -> str:
    value: Any = st.secrets
    try:
        for part in path:
            value = value[part]
        return str(value or "").strip()
    except Exception:
        return default


def supabase_url() -> str:
    return _secret(("supabase", "url"), os.getenv("SUPABASE_URL", ""))


def supabase_anon_key() -> str:
    return _secret(("supabase", "anon_key"), os.getenv("SUPABASE_ANON_KEY", ""))


def supabase_service_key() -> str:
    return _secret(("supabase", "service_role_key"), os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))


def is_supabase_configured() -> bool:
    return bool(supabase_url() and supabase_anon_key())


@lru_cache(maxsize=2)
def _client(url: str, key: str) -> Client:
    return create_client(url, key)


def get_supabase_client(*, service_role: bool = False) -> Client | None:
    url = supabase_url()
    key = supabase_service_key() if service_role else supabase_anon_key()
    if not url or not key:
        return None
    return _client(url, key)


def apply_access_token(client: Client, access_token: str | None, refresh_token: str | None = None) -> None:
    if not access_token:
        return
    try:
        if refresh_token:
            client.auth.set_session(access_token, refresh_token)
        else:
            client.postgrest.auth(access_token)
    except Exception:
        try:
            client.postgrest.auth(access_token)
        except Exception:
            pass

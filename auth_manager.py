from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import time
from typing import Any

import streamlit as st

from supabase_backend import get_supabase_client, is_supabase_configured
from user_context import set_current_user

try:
    import extra_streamlit_components as stx
except Exception:  # pragma: no cover
    stx = None

COOKIE_NAME = "momopro_refresh_token"


@dataclass
class AuthState:
    authenticated: bool
    user_id: str = ""
    email: str = ""
    access_token: str = ""
    refresh_token: str = ""
    expires_at: int = 0


def _cookie_manager():
    if stx is None:
        return None
    if "_momopro_cookie_manager" not in st.session_state:
        st.session_state._momopro_cookie_manager = stx.CookieManager(key="momopro_cookie_manager")
    return st.session_state._momopro_cookie_manager


def _save_session(session: Any) -> AuthState:
    user = getattr(session, "user", None)
    access_token = str(getattr(session, "access_token", "") or "")
    refresh_token = str(getattr(session, "refresh_token", "") or "")
    user_id = str(getattr(user, "id", "") or "")
    email = str(getattr(user, "email", "") or "")
    expires_at = int(getattr(session, "expires_at", 0) or 0)
    if not expires_at and access_token:
        expires_at = _jwt_exp(access_token)
    state = AuthState(bool(user_id), user_id, email, access_token, refresh_token, expires_at)
    st.session_state.momopro_auth = state.__dict__
    set_current_user(user_id or None, email)
    manager = _cookie_manager()
    if manager and refresh_token:
        try:
            manager.set(COOKIE_NAME, refresh_token, max_age=60 * 60 * 24 * 30, key="set_momopro_cookie")
        except Exception:
            pass
    return state



def _jwt_exp(token: str) -> int:
    """Read a JWT expiry without verifying the signature (expiry hint only)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return int(data.get("exp") or 0)
    except Exception:
        return 0


def _token_is_fresh(state: AuthState, minimum_seconds: int = 300) -> bool:
    expiry = int(state.expires_at or _jwt_exp(state.access_token) or 0)
    return bool(state.access_token and expiry > int(time.time()) + minimum_seconds)

def _state_from_session() -> AuthState:
    raw = st.session_state.get("momopro_auth") or {}
    state = AuthState(**{key: raw.get(key, getattr(AuthState(False), key)) for key in AuthState.__dataclass_fields__})
    set_current_user(state.user_id or None, state.email)
    return state


def restore_auth() -> AuthState:
    if not is_supabase_configured():
        set_current_user("local-owner", "local@momopro.ai")
        return AuthState(True, "local-owner", "local@momopro.ai")

    existing = _state_from_session()
    client = get_supabase_client()
    manager = _cookie_manager()

    # Streamlit sessions can survive while the Supabase access token expires. Never
    # trust an authenticated flag alone: refresh before cloud data is loaded.
    if existing.authenticated and _token_is_fresh(existing):
        return existing
    if client and existing.refresh_token:
        try:
            response = client.auth.refresh_session(existing.refresh_token)
            session = getattr(response, "session", None)
            if session:
                return _save_session(session)
        except Exception:
            st.session_state.pop("momopro_auth", None)
            set_current_user(None)

    refresh_token = None
    if manager:
        try:
            refresh_token = manager.get(COOKIE_NAME)
        except Exception:
            refresh_token = None
    if client and refresh_token:
        try:
            response = client.auth.refresh_session(str(refresh_token))
            session = getattr(response, "session", None)
            if session:
                return _save_session(session)
        except Exception:
            pass
    return AuthState(False)


def sign_in(email: str, password: str) -> tuple[AuthState, str]:
    client = get_supabase_client()
    if not client:
        return AuthState(False), "Supabase is not configured."
    try:
        response = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
        session = getattr(response, "session", None)
        if not session:
            return AuthState(False), "Sign-in did not return a session."
        return _save_session(session), ""
    except Exception as exc:
        return AuthState(False), str(exc)


def sign_up(email: str, password: str) -> tuple[AuthState, str]:
    client = get_supabase_client()
    if not client:
        return AuthState(False), "Supabase is not configured."
    try:
        response = client.auth.sign_up({"email": email.strip(), "password": password})
        session = getattr(response, "session", None)
        if session:
            return _save_session(session), ""
        return AuthState(False), "Account created. Check your email to confirm it, then sign in."
    except Exception as exc:
        return AuthState(False), str(exc)


def sign_out() -> None:
    client = get_supabase_client()
    try:
        if client:
            client.auth.sign_out()
    except Exception:
        pass
    st.session_state.pop("momopro_auth", None)
    set_current_user(None)
    manager = _cookie_manager()
    if manager:
        try:
            manager.delete(COOKIE_NAME, key="delete_momopro_cookie")
        except Exception:
            pass


def require_auth() -> AuthState:
    state = restore_auth()
    if state.authenticated:
        return state

    st.title("📈 MomoPro AI")
    st.caption("Sign in to restore your private workspace, plans, journal, and broker history.")
    sign_in_tab, create_tab = st.tabs(["Sign in", "Create account"])
    with sign_in_tab:
        with st.form("momopro_sign_in"):
            email = st.text_input("Email", autocomplete="email")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            new_state, error = sign_in(email, password)
            if new_state.authenticated:
                st.rerun()
            st.error(error or "Unable to sign in.")
    with create_tab:
        with st.form("momopro_sign_up"):
            new_email = st.text_input("Email", key="signup_email", autocomplete="email")
            new_password = st.text_input("Password", key="signup_password", type="password", autocomplete="new-password")
            confirm = st.text_input("Confirm password", type="password", autocomplete="new-password")
            create = st.form_submit_button("Create account", use_container_width=True)
        if create:
            if len(new_password) < 8:
                st.error("Use at least 8 characters.")
            elif new_password != confirm:
                st.error("Passwords do not match.")
            else:
                new_state, message = sign_up(new_email, new_password)
                if new_state.authenticated:
                    st.rerun()
                st.info(message)
    st.stop()

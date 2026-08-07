from __future__ import annotations

import io
import os
import time
from collections import deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests
import streamlit as st

from supabase_backend import apply_access_token, get_supabase_client
from user_context import current_user_id

API_BASE = "https://api.massive.com"
STORAGE_BUCKET = "scanner-data"
STORAGE_OBJECT = "massive_daily_history.parquet"
LOCAL_DIR = Path(os.getenv("MOMOPRO_SCANNER_CACHE", "/tmp/momopro_scanner_v2"))
TARGET_SESSIONS = 270
MINIMUM_READY_SESSIONS = 220
FREE_TIER_CALLS_PER_MINUTE = 5
SAFE_CALL_INTERVAL_SECONDS = 12.5


def _secret(name: str) -> str:
    """Read a top-level Streamlit secret, then fall back to an environment variable."""
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return str(os.getenv(name, "") or "").strip()


def _iter_secret_items(node: Any, path: tuple[str, ...] = ()):
    """Recursively walk Streamlit secrets without ever exposing secret values."""
    try:
        keys = list(node.keys()) if hasattr(node, "keys") else []
    except Exception:
        keys = []
    for key in keys:
        try:
            value = node[key]
        except Exception:
            continue
        current = path + (str(key),)
        if hasattr(value, "keys"):
            yield from _iter_secret_items(value, current)
        else:
            yield current, value


def massive_api_key_with_source() -> tuple[str, str]:
    """Resolve Massive credentials even when TOML section scope nests the key unexpectedly.

    Streamlit TOML has an easy-to-miss rule: after a section header such as [webull],
    later key/value lines remain inside that section. A line that visually reads
    MASSIVE_API_KEY = "..." may therefore not be a top-level key. We search the
    complete secret tree by key name so this cannot silently break Scanner v2.
    """
    aliases = {
        "massive_api_key",
        "massive_key",
        "api_key",
        "apikey",
    }

    # Prefer the documented top-level name.
    for name in ("MASSIVE_API_KEY", "MASSIVE_KEY", "massive_api_key"):
        value = _secret(name)
        if value:
            return value, f"Streamlit/env:{name}"

    # Prefer an explicit [massive] table next.
    try:
        section = st.secrets.get("massive", {})
        if hasattr(section, "get"):
            for name in ("api_key", "API_KEY", "key", "apiKey", "MASSIVE_API_KEY"):
                value = section.get(name, "")
                if value:
                    return str(value).strip(), f"Streamlit:massive.{name}"
    except Exception:
        pass

    # Finally search all nested tables for an explicitly named Massive key.
    # We intentionally do NOT accept a generic api_key outside a [massive] table,
    # because other providers (Alpaca/OpenAI/etc.) also use that label.
    try:
        for path, value in _iter_secret_items(st.secrets):
            leaf = path[-1].strip().lower() if path else ""
            if leaf in {"massive_api_key", "massive_key"}:
                cleaned = str(value or "").strip()
                if cleaned:
                    return cleaned, "Streamlit:" + ".".join(path)
    except Exception:
        pass

    return "", "not found"


def massive_api_key() -> str:
    return massive_api_key_with_source()[0]


def test_massive_connection() -> tuple[bool, str]:
    """One lightweight authenticated request used only by the setup UI."""
    key = massive_api_key()
    if not key:
        return False, "No Massive API key was found in Streamlit Secrets."
    try:
        response = requests.get(
            f"{API_BASE}/v3/reference/tickers/types",
            params={"asset_class": "stocks", "locale": "us", "apiKey": key},
            timeout=(5, 15),
        )
        if response.status_code in {401, 403}:
            return False, "Massive found the key but rejected it. Re-copy the API key from your Massive dashboard."
        if response.status_code == 429:
            return False, "Massive recognized the request but the free-tier rate limit is temporarily exhausted. Wait one minute and test again."
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("status", "")).upper() not in {"OK", "DELAYED"}:
            return False, str(payload.get("error") or payload.get("message") or "Massive returned an unsuccessful response.")
        return True, "Massive API connection verified."
    except requests.Timeout:
        return False, "Massive connection test timed out after 15 seconds."
    except Exception as exc:
        return False, f"Massive connection test failed: {exc}"


def _auth_token() -> str | None:
    try:
        auth = st.session_state.get("momopro_auth") or {}
        if isinstance(auth, dict):
            token = str(auth.get("access_token") or "").strip()
            return token or None
    except Exception:
        pass
    return None


def _user_cache_path() -> Path:
    user = current_user_id() or "anonymous"
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    safe = re_sub(r"[^A-Za-z0-9_-]", "_", str(user))
    return LOCAL_DIR / f"{safe}_{STORAGE_OBJECT}"


def re_sub(pattern: str, repl: str, value: str) -> str:
    import re
    return re.sub(pattern, repl, value)


def _cloud_path() -> str:
    return f"{current_user_id() or 'anonymous'}/{STORAGE_OBJECT}"


def _normalise_frame(frame: pd.DataFrame) -> pd.DataFrame:
    expected = ["date", "symbol", "open", "high", "low", "close", "volume", "vwap", "transactions"]
    if frame is None or frame.empty:
        return pd.DataFrame(columns=expected)
    out = frame.copy()
    for column in expected:
        if column not in out.columns:
            out[column] = pd.NA
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date
    out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    for column in ["open", "high", "low", "close", "volume", "vwap", "transactions"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out = out.dropna(subset=["date", "symbol", "close"])
    out = out.drop_duplicates(["date", "symbol"], keep="last")
    return out[expected].sort_values(["symbol", "date"]).reset_index(drop=True)


def load_history(*, force_cloud: bool = False) -> pd.DataFrame:
    path = _user_cache_path()
    if path.exists() and not force_cloud:
        try:
            return _normalise_frame(pd.read_parquet(path))
        except Exception:
            path.unlink(missing_ok=True)

    client = get_supabase_client()
    if client and current_user_id():
        try:
            apply_access_token(client, _auth_token())
            payload = client.storage.from_(STORAGE_BUCKET).download(_cloud_path())
            if payload:
                path.write_bytes(payload)
                return _normalise_frame(pd.read_parquet(path))
        except Exception:
            pass
    return _normalise_frame(pd.DataFrame())


def save_history(frame: pd.DataFrame) -> tuple[bool, str]:
    frame = _normalise_frame(frame)
    path = _user_cache_path()
    frame.to_parquet(path, index=False, compression="zstd")

    client = get_supabase_client()
    if not client or not current_user_id():
        return False, "Saved locally, but Supabase Storage is unavailable."
    try:
        apply_access_token(client, _auth_token())
        data = path.read_bytes()
        bucket = client.storage.from_(STORAGE_BUCKET)
        options = {"content-type": "application/octet-stream", "upsert": "true"}
        try:
            bucket.upload(_cloud_path(), data, options)
        except Exception:
            try:
                bucket.update(_cloud_path(), data, options)
            except Exception:
                bucket.remove([_cloud_path()])
                bucket.upload(_cloud_path(), data, options)
        return True, "Saved locally and to Supabase Storage."
    except Exception as exc:
        return False, f"Saved locally, but cloud upload failed: {exc}"


def fetch_market_day(session_date: date, *, api_key: str | None = None) -> pd.DataFrame:
    key = api_key or massive_api_key()
    if not key:
        raise RuntimeError("MASSIVE_API_KEY is missing from Streamlit Secrets.")
    url = f"{API_BASE}/v2/aggs/grouped/locale/us/market/stocks/{session_date.isoformat()}"
    response = requests.get(
        url,
        params={"adjusted": "true", "include_otc": "false", "apiKey": key},
        timeout=(10, 45),
    )
    if response.status_code == 429:
        raise RuntimeError("Massive free-tier rate limit reached. Wait one minute and continue.")
    response.raise_for_status()
    payload = response.json()
    if str(payload.get("status", "")).upper() not in {"OK", "DELAYED"}:
        raise RuntimeError(payload.get("error") or payload.get("message") or "Massive returned an unsuccessful response.")
    rows = []
    for item in payload.get("results") or []:
        symbol = str(item.get("T") or "").upper().strip()
        if not symbol or item.get("c") is None:
            continue
        rows.append({
            "date": session_date,
            "symbol": symbol,
            "open": item.get("o"),
            "high": item.get("h"),
            "low": item.get("l"),
            "close": item.get("c"),
            "volume": item.get("v"),
            "vwap": item.get("vw"),
            "transactions": item.get("n"),
        })
    return _normalise_frame(pd.DataFrame(rows))


def history_status(frame: pd.DataFrame | None = None) -> dict[str, Any]:
    data = load_history() if frame is None else _normalise_frame(frame)
    sessions = sorted(set(data["date"])) if not data.empty else []
    return {
        "configured": bool(massive_api_key()),
        "sessions": len(sessions),
        "symbols": int(data["symbol"].nunique()) if not data.empty else 0,
        "rows": len(data),
        "earliest": sessions[0].isoformat() if sessions else None,
        "latest": sessions[-1].isoformat() if sessions else None,
        "ready": len(sessions) >= MINIMUM_READY_SESSIONS,
        "target": TARGET_SESSIONS,
        "missing": max(0, TARGET_SESSIONS - len(sessions)),
    }


def _candidate_dates(existing: set[date], target_sessions: int) -> list[date]:
    dates: list[date] = []
    cursor = datetime.now(timezone.utc).date()
    # Free plan is end-of-day. Start with yesterday so an incomplete current day
    # never contaminates daily indicators.
    cursor -= timedelta(days=1)
    while len(existing) + len(dates) < target_sessions and len(dates) < target_sessions * 2:
        if cursor.weekday() < 5 and cursor not in existing:
            dates.append(cursor)
        cursor -= timedelta(days=1)
    return dates


def build_or_update_history(
    *,
    target_sessions: int = TARGET_SESSIONS,
    progress: Callable[[dict[str, Any]], None] | None = None,
    max_requests: int | None = None,
) -> dict[str, Any]:
    """Build a resumable whole-market daily database on the free plan.

    The free plan allows five calls per minute. We deliberately remain below
    that limit. Every successful market day is appended and saved periodically,
    so closing the tab or a restart does not erase completed work.
    """
    data = load_history()
    existing = set(data["date"]) if not data.empty else set()
    dates = _candidate_dates(existing, target_sessions)
    if max_requests is not None:
        dates = dates[: max(0, int(max_requests))]

    successful = 0
    attempted = 0
    empty_days = 0
    errors: list[str] = []
    last_call = 0.0

    for idx, session_date in enumerate(dates, start=1):
        elapsed = time.monotonic() - last_call
        if last_call and elapsed < SAFE_CALL_INTERVAL_SECONDS:
            time.sleep(SAFE_CALL_INTERVAL_SECONDS - elapsed)
        attempted += 1
        try:
            day = fetch_market_day(session_date)
            last_call = time.monotonic()
            if day.empty:
                empty_days += 1
            else:
                data = pd.concat([data, day], ignore_index=True)
                data = _normalise_frame(data)
                existing.add(session_date)
                successful += 1
                if successful % 5 == 0:
                    save_history(data)
        except Exception as exc:
            last_call = time.monotonic()
            errors.append(f"{session_date}: {exc}")
            if "rate limit" in str(exc).lower():
                save_history(data)
                break

        state = history_status(data)
        state.update({"attempted": attempted, "successful": successful, "current_date": session_date.isoformat(), "errors": errors[-3:]})
        if progress:
            progress(state)
        if state["sessions"] >= target_sessions:
            break

    cloud_saved, save_message = save_history(data)
    result = history_status(data)
    result.update({
        "attempted": attempted,
        "successful": successful,
        "empty_days": empty_days,
        "errors": errors,
        "cloud_saved": cloud_saved,
        "save_message": save_message,
    })
    return result


def render_scanner_v2_setup() -> None:
    """Render non-blocking Scanner v2 setup/status.

    The one-time free-tier history bootstrap is owned by scanner_runtime and
    executes in its own worker thread. This UI never performs the hour-long
    bootstrap inline, so Dashboard/navigation remain responsive.
    """
    key_value, key_source = massive_api_key_with_source()
    configured = bool(key_value)
    if not configured:
        with st.expander("Scanner v2 Market Database", expanded=True):
            st.error("Massive API key not detected. Scanner v2 cannot build its market database yet.")
            st.caption("Accepted secret: MASSIVE_API_KEY = \"...\" (nested locations are also detected).")
        return

    from scanner_runtime import ensure_bootstrap_started, job_state, local_manifest
    uid = str(current_user_id() or "anonymous")
    manifest = local_manifest(uid)
    if not manifest.get("ready"):
        ensure_bootstrap_started()
    state = job_state("bootstrap", uid)
    sessions = int(manifest.get("sessions") or state.get("progress") or 0)
    ready = bool(manifest.get("ready") or state.get("ready"))

    with st.expander("Scanner v2 Market Database", expanded=not ready):
        st.success("Massive API key detected by MomoPro.")
        st.caption(f"Credential source: {key_source} (value hidden)")
        cols = st.columns(4)
        cols[0].metric("Stored sessions", f"{sessions}/{TARGET_SESSIONS}")
        cols[1].metric("Status", "Ready" if ready else ("Building in background" if state.get("running") else "Preparing"))
        cols[2].metric("Latest day", str(manifest.get("latest") or "Building"))
        cols[3].metric("Symbols", f"{int(manifest.get('symbols') or 0):,}")
        if ready:
            st.success("Scanner v2 history is ready. Normal scans now use local calculations and only update missing market data.")
        else:
            pct = min(1.0, sessions / max(1, MINIMUM_READY_SESSIONS))
            st.progress(pct)
            st.info(
                "The one-time consolidated-history build is running independently from the rest of MomoPro. "
                "You can use Dashboard, Watchlist, Live Chart and every other page while it continues."
            )
            if state.get("stage"):
                st.caption(str(state.get("stage")))
            if state.get("error"):
                st.warning(f"Last Scanner v2 history message: {state.get('error')}")
        if st.button("Test Massive API connection", key="scanner_v2_test_massive"):
            ok, detail = test_massive_connection()
            (st.success if ok else st.error)(detail)

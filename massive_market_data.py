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
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:
        return str(os.getenv(name, "") or "").strip()


def massive_api_key() -> str:
    return _secret("MASSIVE_API_KEY")


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
    status = history_status()
    with st.expander("Scanner v2 Market Database", expanded=not status["ready"]):
        if not status["configured"]:
            st.error("Add MASSIVE_API_KEY to Streamlit Secrets before building Scanner v2 history.")
            return
        cols = st.columns(4)
        cols[0].metric("Stored sessions", f"{status['sessions']}/{status['target']}")
        cols[1].metric("Symbols", f"{status['symbols']:,}")
        cols[2].metric("Latest day", status["latest"] or "Not built")
        cols[3].metric("Status", "Ready" if status["ready"] else "Setup needed")

        if status["ready"]:
            st.success("Scanner v2 has enough persistent history for EMA200 and full-market ranking.")
            label = "Update Scanner v2 Database"
        else:
            remaining = status["missing"]
            estimated = int((remaining * SAFE_CALL_INTERVAL_SECONDS) / 60)
            st.info(
                f"One-time setup still needs about {remaining} trading sessions. "
                f"On the free plan this can take roughly {estimated} minutes. "
                "Progress is saved every few days and can resume after interruption."
            )
            label = "Build / Continue Scanner v2 Database"

        if st.button(label, key="scanner_v2_build_history", type="primary", width="stretch"):
            bar = st.progress(0.0)
            message = st.empty()
            initial = max(1, status["sessions"])

            def update(progress_state: dict[str, Any]) -> None:
                completed = progress_state.get("sessions", 0)
                bar.progress(min(1.0, completed / TARGET_SESSIONS))
                message.info(
                    f"Stored {completed}/{TARGET_SESSIONS} sessions — "
                    f"currently checking {progress_state.get('current_date', '—')}."
                )

            try:
                result = build_or_update_history(progress=update)
                if result["ready"]:
                    st.success("Scanner v2 market database is ready.")
                else:
                    st.warning(
                        f"Saved {result['sessions']} sessions. Run Continue again if setup stopped or was interrupted. "
                        f"{result['save_message']}"
                    )
                st.rerun()
            except Exception as exc:
                st.error(f"Scanner v2 history setup stopped safely: {exc}")

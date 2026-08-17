from __future__ import annotations

import json
import logging
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

from massive_market_data import (
    MINIMUM_READY_SESSIONS,
    TARGET_SESSIONS,
    SAFE_CALL_INTERVAL_SECONDS,
    fetch_market_day,
    massive_api_key,
)
from scanner_v2 import run_scan_v2
from supabase_backend import supabase_anon_key, supabase_url
from user_context import current_user_id

LOGGER = logging.getLogger("momopro.scanner_v2")

# Scanner v2 owns a dedicated executor. No whole-market work is executed by
# automatic_loading.py or a Streamlit fragment.
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="momopro-scanner-v2")
_HISTORY_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="momopro-scanner-history")
_LOCK = threading.RLock()
_HEAVY_WORK_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}

BASE_DIR = Path(os.getenv("MOMOPRO_SCANNER_CACHE", "/tmp/momopro_scanner_v2"))
HISTORY_NAME = "massive_daily_history.parquet"
SCAN_NAME = "latest_scan.parquet"
MANIFEST_NAME = "scanner_manifest.json"
STORAGE_BUCKET = "scanner-data"
HISTORY_FOLDER = "history-days"
LIVE_SCAN_TTL_MINUTES = 5
LIVE_PRICE_TTL_SECONDS = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_user(user_id: str | None) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(user_id or "anonymous"))


def _user_root(user_id: str | None) -> Path:
    root = BASE_DIR / _safe_user(user_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _paths(user_id: str | None) -> tuple[Path, Path, Path]:
    root = _user_root(user_id)
    return root / HISTORY_NAME, root / SCAN_NAME, root / MANIFEST_NAME


def _day_dir(user_id: str | None) -> Path:
    path = _user_root(user_id) / HISTORY_FOLDER
    path.mkdir(parents=True, exist_ok=True)
    return path


def _day_path(user_id: str | None, session_date: date) -> Path:
    return _day_dir(user_id) / f"{session_date.isoformat()}.parquet"


def _cloud_object(user_id: str, filename: str) -> str:
    return f"{user_id}/{filename}"


def _cloud_day_object(user_id: str, session_date: date) -> str:
    return f"{user_id}/{HISTORY_FOLDER}/{session_date.isoformat()}.parquet"


def _auth_token() -> str:
    try:
        auth = st.session_state.get("momopro_auth") or {}
        if isinstance(auth, dict):
            return str(auth.get("access_token") or "").strip()
    except Exception:
        pass
    return ""


def _context() -> dict[str, str]:
    auth = st.session_state.get("momopro_auth") or {}
    refresh_token = str(auth.get("refresh_token") or "").strip() if isinstance(auth, dict) else ""
    return {
        "user_id": str(current_user_id() or "anonymous"),
        "massive_key": massive_api_key(),
        "supabase_url": supabase_url(),
        "supabase_key": supabase_anon_key(),
        "access_token": _auth_token(),
        "refresh_token": refresh_token,
        "alpaca_key": str(st.secrets.get("ALPACA_API_KEY", "") or "").strip(),
        "alpaca_secret": str(st.secrets.get("ALPACA_SECRET_KEY", "") or "").strip(),
    }


def _normalise_history(frame: pd.DataFrame) -> pd.DataFrame:
    expected = ["date", "symbol", "open", "high", "low", "close", "volume", "vwap", "transactions"]
    if frame is None or frame.empty:
        return pd.DataFrame(columns=expected)
    out = frame.copy()
    for col in expected:
        if col not in out.columns:
            out[col] = pd.NA
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date
    out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    for col in ["open", "high", "low", "close", "volume", "vwap", "transactions"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return (
        out.dropna(subset=["date", "symbol", "close"])
        .drop_duplicates(["date", "symbol"], keep="last")[expected]
        .sort_values(["symbol", "date"])
        .reset_index(drop=True)
    )


def _manifest_from_history(history: pd.DataFrame) -> dict[str, Any]:
    if history is None or history.empty:
        return {
            "sessions": 0, "symbols": 0, "rows": 0, "ready": False,
            "latest": None, "target": TARGET_SESSIONS, "completed_dates": [],
        }
    dates = pd.to_datetime(history["date"], errors="coerce").dropna()
    unique_dates = sorted({d.isoformat() for d in dates.dt.date})
    sessions = len(unique_dates)
    return {
        "sessions": sessions,
        "symbols": int(history["symbol"].nunique()),
        "rows": int(len(history)),
        "ready": sessions >= MINIMUM_READY_SESSIONS,
        "latest": unique_dates[-1] if unique_dates else None,
        "target": TARGET_SESSIONS,
        "completed_dates": unique_dates,
    }


def _write_manifest(user_id: str, manifest: dict[str, Any]) -> None:
    _, _, manifest_path = _paths(user_id)
    payload = dict(manifest)
    payload["updated_at"] = _now()
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def local_manifest(user_id: str | None = None) -> dict[str, Any]:
    uid = str(user_id or current_user_id() or "anonymous")
    _, _, manifest_path = _paths(uid)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _make_cloud_client(ctx: dict[str, str]):
    if not ctx.get("supabase_url") or not ctx.get("supabase_key") or ctx.get("user_id") in {"", "anonymous"}:
        return None
    try:
        from supabase import create_client
        client = create_client(ctx["supabase_url"], ctx["supabase_key"])
        token = ctx.get("access_token") or ""
        refresh = ctx.get("refresh_token") or ""
        if token:
            try:
                if refresh:
                    client.auth.set_session(token, refresh)
                else:
                    client.postgrest.auth(token)
            except Exception:
                try:
                    client.postgrest.auth(token)
                except Exception:
                    pass
        return client
    except Exception:
        return None


def _cloud_download(ctx: dict[str, str], filename: str, destination: Path) -> bool:
    client = _make_cloud_client(ctx)
    if client is None:
        return False
    try:
        payload = client.storage.from_(STORAGE_BUCKET).download(_cloud_object(ctx["user_id"], filename))
        if payload:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            return True
    except Exception as exc:
        LOGGER.debug("Scanner cloud download miss %s: %s", filename, exc)
    return False


def _cloud_upload(ctx: dict[str, str], filename: str, source: Path) -> bool:
    client = _make_cloud_client(ctx)
    if client is None or not source.exists():
        return False
    try:
        bucket = client.storage.from_(STORAGE_BUCKET)
        data = source.read_bytes()
        options = {"content-type": "application/octet-stream", "upsert": "true"}
        object_name = _cloud_object(ctx["user_id"], filename)
        try:
            bucket.upload(object_name, data, options)
        except Exception:
            bucket.update(object_name, data, options)
        return True
    except Exception as exc:
        LOGGER.warning("Scanner cloud upload failed for %s: %s", filename, exc)
        return False


def _cloud_download_day(ctx: dict[str, str], session_date: date, destination: Path) -> bool:
    client = _make_cloud_client(ctx)
    if client is None:
        return False
    try:
        payload = client.storage.from_(STORAGE_BUCKET).download(_cloud_day_object(ctx["user_id"], session_date))
        if payload:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            return True
    except Exception:
        pass
    return False


def _cloud_upload_day(ctx: dict[str, str], session_date: date, source: Path) -> bool:
    client = _make_cloud_client(ctx)
    if client is None or not source.exists():
        return False
    try:
        bucket = client.storage.from_(STORAGE_BUCKET)
        data = source.read_bytes()
        options = {"content-type": "application/octet-stream", "upsert": "true"}
        object_name = _cloud_day_object(ctx["user_id"], session_date)
        try:
            bucket.upload(object_name, data, options)
        except Exception:
            bucket.update(object_name, data, options)
        return True
    except Exception as exc:
        LOGGER.warning("Scanner day upload failed %s: %s", session_date, exc)
        return False


def _restore_manifest(ctx: dict[str, str]) -> dict[str, Any]:
    _, _, manifest_path = _paths(ctx["user_id"])
    if not manifest_path.exists():
        _cloud_download(ctx, MANIFEST_NAME, manifest_path)
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _save_manifest_explicit(ctx: dict[str, str], manifest: dict[str, Any], *, cloud: bool = True) -> dict[str, Any]:
    _write_manifest(ctx["user_id"], manifest)
    if cloud:
        _, _, manifest_path = _paths(ctx["user_id"])
        _cloud_upload(ctx, MANIFEST_NAME, manifest_path)
    return manifest


def _save_day_explicit(ctx: dict[str, str], session_date: date, frame: pd.DataFrame) -> None:
    path = _day_path(ctx["user_id"], session_date)
    clean = _normalise_history(frame)
    clean.to_parquet(path, index=False, compression="zstd")
    if not _cloud_upload_day(ctx, session_date, path):
        raise RuntimeError(f"Scanner v2 could not persist {session_date.isoformat()} to Supabase Storage.")


def _completed_dates(manifest: dict[str, Any]) -> set[date]:
    out: set[date] = set()
    for value in manifest.get("completed_dates") or []:
        try:
            out.add(date.fromisoformat(str(value)))
        except Exception:
            pass
    return out


def _candidate_dates(existing: set[date], target: int) -> list[date]:
    """Return a generous pool of older weekday candidates.

    A candidate date is not the same thing as a valid trading session: U.S.
    market holidays and occasional empty/provider-error days must not consume
    the remaining quota.  Generate enough lookback headroom for the bootstrap
    worker to keep walking backward until it has *target* successful sessions.
    """
    cursor = datetime.now(timezone.utc).date() - timedelta(days=1)
    dates: list[date] = []
    missing = max(0, int(target) - len(existing))
    # Roughly 252 trading sessions exist in a calendar year.  Eight missing
    # sessions can easily intersect several holidays, so give the worker ample
    # headroom without allowing an unbounded loop.
    max_candidates = max(40, missing * 6)
    while len(dates) < max_candidates:
        if cursor.weekday() < 5 and cursor not in existing:
            dates.append(cursor)
        cursor -= timedelta(days=1)
    return dates


def _load_history_explicit(ctx: dict[str, str]) -> pd.DataFrame:
    history_path, _, _ = _paths(ctx["user_id"])
    if history_path.exists():
        try:
            return _normalise_history(pd.read_parquet(history_path))
        except Exception:
            history_path.unlink(missing_ok=True)
    if _cloud_download(ctx, HISTORY_NAME, history_path):
        try:
            return _normalise_history(pd.read_parquet(history_path))
        except Exception:
            history_path.unlink(missing_ok=True)

    # Recovery path for a bootstrap that was interrupted before compaction.
    manifest = _restore_manifest(ctx)
    frames: list[pd.DataFrame] = []
    for session_date in sorted(_completed_dates(manifest)):
        path = _day_path(ctx["user_id"], session_date)
        if not path.exists():
            _cloud_download_day(ctx, session_date, path)
        if path.exists():
            try:
                frames.append(pd.read_parquet(path))
            except Exception:
                pass
    return _normalise_history(pd.concat(frames, ignore_index=True)) if frames else _normalise_history(pd.DataFrame())


def _compact_history(ctx: dict[str, str], manifest: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames: list[pd.DataFrame] = []
    completed = sorted(_completed_dates(manifest))
    for index, session_date in enumerate(completed, 1):
        path = _day_path(ctx["user_id"], session_date)
        if not path.exists():
            _cloud_download_day(ctx, session_date, path)
        if path.exists():
            try:
                frames.append(pd.read_parquet(path))
            except Exception as exc:
                LOGGER.warning("Scanner shard read failed %s: %s", session_date, exc)
        if index % 25 == 0:
            _update_job(f"bootstrap:{ctx['user_id']}", stage=f"Compacting saved history ({index}/{len(completed)})")
    history = _normalise_history(pd.concat(frames, ignore_index=True)) if frames else _normalise_history(pd.DataFrame())
    history_path, _, _ = _paths(ctx["user_id"])
    history.to_parquet(history_path, index=False, compression="zstd")
    compact_manifest = _manifest_from_history(history)
    compact_manifest["completed_dates"] = [d.isoformat() for d in completed]
    _save_manifest_explicit(ctx, compact_manifest, cloud=True)
    if not _cloud_upload(ctx, HISTORY_NAME, history_path):
        LOGGER.warning("Scanner compact history cloud upload failed; local compact history remains usable for this process.")
    return history, compact_manifest


def _update_job(key: str, **fields: Any) -> None:
    with _LOCK:
        state = dict(_JOBS.get(key) or {})
        state.update(fields)
        state["updated_at"] = _now()
        _JOBS[key] = state


def job_state(kind: str, user_id: str | None = None) -> dict[str, Any]:
    uid = str(user_id or current_user_id() or "anonymous")
    key = f"{kind}:{uid}"
    with _LOCK:
        state = dict(_JOBS.get(key) or {})
        future = state.get("future")
        if isinstance(future, Future):
            state["running"] = not future.done()
            if future.done() and future.exception() is not None and not state.get("error"):
                state["error"] = str(future.exception())
            state.pop("future", None)
        return state


def _bootstrap_worker(ctx: dict[str, str]) -> dict[str, Any]:
    key = f"bootstrap:{ctx['user_id']}"
    manifest = _restore_manifest(ctx)
    completed = _completed_dates(manifest)

    # Backward compatibility: if the previous implementation created a compact
    # history but not completed_dates, derive durable progress from that file.
    if not completed:
        history = _load_history_explicit(ctx)
        if not history.empty:
            derived = _manifest_from_history(history)
            completed = _completed_dates(derived)
            manifest = derived
            _save_manifest_explicit(ctx, manifest, cloud=True)

    dates = _candidate_dates(completed, MINIMUM_READY_SESSIONS)
    _update_job(
        key,
        stage="Downloading consolidated daily market history",
        progress=len(completed),
        total=MINIMUM_READY_SESSIONS,
        error="",
    )
    LOGGER.info("Scanner bootstrap start user=%s completed=%s needed=%s", ctx["user_id"], len(completed), MINIMUM_READY_SESSIONS)

    last_call = 0.0
    for session_date in dates:
        if len(completed) >= MINIMUM_READY_SESSIONS:
            break
        elapsed = time.monotonic() - last_call
        if last_call and elapsed < SAFE_CALL_INTERVAL_SECONDS:
            time.sleep(SAFE_CALL_INTERVAL_SECONDS - elapsed)
        try:
            LOGGER.info("Scanner Massive fetch %s (%s/%s)", session_date, len(completed) + 1, MINIMUM_READY_SESSIONS)
            day = fetch_market_day(session_date, api_key=ctx["massive_key"])
            last_call = time.monotonic()
            if day.empty:
                LOGGER.info("Scanner Massive returned empty market day %s", session_date)
                _update_job(key, current_date=session_date.isoformat(), note="No market data returned; skipped")
                continue

            # Durable checkpoint: persist this market day BEFORE counting it as
            # completed. A Streamlit sleep/redeploy can then resume exactly here.
            _save_day_explicit(ctx, session_date, day)
            completed.add(session_date)
            manifest = {
                "sessions": len(completed),
                "symbols": int(day["symbol"].nunique()),
                "rows": int(manifest.get("rows") or 0) + int(len(day)),
                "ready": len(completed) >= MINIMUM_READY_SESSIONS,
                "latest": max(completed).isoformat() if completed else None,
                "target": TARGET_SESSIONS,
                "completed_dates": [d.isoformat() for d in sorted(completed)],
                "last_saved_session": session_date.isoformat(),
            }
            _save_manifest_explicit(ctx, manifest, cloud=True)
            LOGGER.info("Scanner saved session %s; durable sessions=%s", session_date, len(completed))
            _update_job(
                key,
                stage="Downloading consolidated daily market history",
                progress=len(completed),
                total=MINIMUM_READY_SESSIONS,
                current_date=session_date.isoformat(),
                last_saved_session=session_date.isoformat(),
                ready=bool(manifest.get("ready")),
                error="",
            )
        except Exception as exc:
            last_call = time.monotonic()
            msg = str(exc)
            LOGGER.exception("Scanner bootstrap failed on %s: %s", session_date, msg)
            _update_job(key, error=msg, current_date=session_date.isoformat())
            if "429" in msg or "rate limit" in msg.lower():
                time.sleep(61)
            else:
                time.sleep(3)

    if len(completed) < MINIMUM_READY_SESSIONS:
        manifest = dict(manifest or {})
        manifest.update({
            "sessions": len(completed),
            "ready": False,
            "completed_dates": [d.isoformat() for d in sorted(completed)],
            "target": TARGET_SESSIONS,
        })
        _save_manifest_explicit(ctx, manifest, cloud=True)
        _update_job(key, stage="History paused — retry will continue from saved sessions", progress=len(completed), total=MINIMUM_READY_SESSIONS, ready=False, done=True)
        return manifest

    _update_job(key, stage="Compacting durable market history", progress=len(completed), total=MINIMUM_READY_SESSIONS)
    history, manifest = _compact_history(ctx, manifest)
    _update_job(
        key,
        stage="History ready",
        progress=int(manifest.get("sessions") or len(completed)),
        total=MINIMUM_READY_SESSIONS,
        ready=True,
        done=True,
        finished_at=_now(),
    )
    LOGGER.info("Scanner history ready sessions=%s symbols=%s", manifest.get("sessions"), manifest.get("symbols"))

    # Produce the first usable candidate list immediately. The user should not
    # have to revisit the page or press a button after a one-time bootstrap.
    try:
        _scan_worker(ctx, history_override=history, skip_incremental=True)
    except Exception as exc:
        LOGGER.exception("Scanner first scan after bootstrap failed: %s", exc)
        _update_job(f"scan:{ctx['user_id']}", done=True, running=False, error=str(exc), stage="First scan failed")
    return manifest


def ensure_bootstrap_started() -> dict[str, Any]:
    ctx = _context()
    uid = ctx["user_id"]
    key = f"bootstrap:{uid}"
    if not ctx.get("massive_key"):
        return {"running": False, "error": "Massive API key not configured."}

    manifest = _restore_manifest(ctx)
    if manifest and not local_manifest(uid):
        _save_manifest_explicit(ctx, manifest, cloud=False)
    if manifest.get("ready"):
        return {**manifest, "running": False, "done": True}

    with _LOCK:
        existing = _JOBS.get(key) or {}
        future = existing.get("future")
        if isinstance(future, Future) and not future.done():
            return job_state("bootstrap", uid)
        future = _EXECUTOR.submit(_bootstrap_worker, ctx)
        _JOBS[key] = {
            "future": future,
            "running": True,
            "stage": "Starting Scanner v2 history",
            "progress": int(manifest.get("sessions") or 0),
            "total": MINIMUM_READY_SESSIONS,
            "started_at": _now(),
        }
    return job_state("bootstrap", uid)


def _latest_completed_date() -> date:
    """Latest U.S. regular session that should be durable in EOD history.

    Use New York market time rather than UTC. Before the regular session has
    safely closed, yesterday is the newest completed day; after 4:15 p.m. ET,
    today can be persisted. Weekends roll back to Friday.
    """
    now_et = datetime.now(ZoneInfo("America/New_York"))
    cursor = now_et.date()
    if now_et.weekday() >= 5 or now_et.time() < dt_time(16, 15):
        cursor -= timedelta(days=1)
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def _incremental_history_update(ctx: dict[str, str], history: pd.DataFrame) -> pd.DataFrame:
    """Append every missing completed session without blocking live scanning.

    A failed/empty EOD request must never prevent the current Alpaca overlay
    from running. Every successful day is checkpointed immediately to local +
    cloud compact history so Streamlit restarts cannot lose the update.
    """
    if history.empty:
        return history

    existing = set(history["date"])
    latest = max(existing)
    target = _latest_completed_date()
    missing: list[date] = []
    cursor = latest + timedelta(days=1)
    while cursor <= target:
        if cursor.weekday() < 5 and cursor not in existing:
            missing.append(cursor)
        cursor += timedelta(days=1)
    if not missing:
        return history

    key = f"scan:{ctx['user_id']}"
    last_call = 0.0
    successes = 0
    for idx, session_date in enumerate(missing, 1):
        elapsed = time.monotonic() - last_call
        if last_call and elapsed < SAFE_CALL_INTERVAL_SECONDS:
            time.sleep(SAFE_CALL_INTERVAL_SECONDS - elapsed)
        _update_job(
            key,
            stage=f"Updating completed market history ({idx}/{len(missing)})",
            progress=min(0.10, 0.04 + (0.06 * idx / max(1, len(missing)))),
        )
        try:
            day = fetch_market_day(session_date, api_key=ctx["massive_key"])
            last_call = time.monotonic()
            if day.empty:
                LOGGER.info("Massive returned no completed data for %s; live scan will continue.", session_date)
                continue
            history = _normalise_history(pd.concat([history, day], ignore_index=True))
            existing.add(session_date)
            successes += 1

            # Persist each successful completed session immediately.
            history_path, _, _ = _paths(ctx["user_id"])
            history.to_parquet(history_path, index=False, compression="zstd")
            manifest = _manifest_from_history(history)
            manifest["last_saved_session"] = max(existing).isoformat()
            _save_manifest_explicit(ctx, manifest, cloud=True)
            _cloud_upload(ctx, HISTORY_NAME, history_path)
            LOGGER.info("Scanner incremental history saved %s", session_date)
        except Exception as exc:
            last_call = time.monotonic()
            LOGGER.warning("Scanner incremental history update failed %s: %s", session_date, exc)
            # Do not break: a provider miss must not strand the current scan.
            continue

    if successes == 0:
        _update_job(key, stage="Completed-day update unavailable; continuing with live current-session data", progress=0.10)
    return history



def _latest_completed_market_date() -> date:
    """Newest regular U.S. session that is safe to treat as completed."""
    now_et = datetime.now(ZoneInfo("America/New_York"))
    cursor = now_et.date()

    # Give the official close/aggregate pipeline a small settlement buffer.
    if now_et.weekday() >= 5 or now_et.time() < dt_time(16, 15):
        cursor -= timedelta(days=1)

    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def _market_sessions(
    ctx: dict[str, str],
    *,
    start_date: date,
    end_date: date,
) -> list[date]:
    """Return actual U.S. exchange sessions, preferring Alpaca's calendar."""
    if start_date > end_date:
        return []

    key = ctx.get("alpaca_key") or ""
    secret = ctx.get("alpaca_secret") or ""

    if key and secret:
        try:
            response = requests.get(
                "https://api.alpaca.markets/v2/calendar",
                headers={
                    "APCA-API-KEY-ID": key,
                    "APCA-API-SECRET-KEY": secret,
                },
                params={
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                timeout=(5, 15),
            )
            response.raise_for_status()
            payload = response.json()
            sessions: list[date] = []
            for item in payload if isinstance(payload, list) else []:
                raw = item.get("date") if isinstance(item, dict) else None
                if raw:
                    try:
                        sessions.append(date.fromisoformat(str(raw)))
                    except Exception:
                        pass
            if sessions:
                return sorted(set(sessions))
        except Exception as exc:
            LOGGER.info("Alpaca calendar unavailable; weekday fallback used: %s", exc)

    sessions: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        if cursor.weekday() < 5:
            sessions.append(cursor)
        cursor += timedelta(days=1)
    return sessions


def _history_rollover_state(ctx: dict[str, str]) -> dict[str, Any]:
    """Determine EOD freshness from the lightweight manifest only.

    Previous ZIP 50 logic reloaded the full Scanner history on every Streamlit
    rerun simply to answer "are we behind?". With 220+ sessions and ~14k
    symbols/day that caused large repeated allocations and could exhaust the
    Streamlit worker after the app had been open for a while.
    """
    manifest = _restore_manifest(ctx)
    target = _latest_completed_market_date()

    latest_raw = (
        manifest.get("last_saved_session")
        or manifest.get("latest")
    )
    latest = None
    if latest_raw:
        try:
            latest = date.fromisoformat(str(latest_raw)[:10])
        except Exception:
            latest = None

    sessions = int(manifest.get("sessions") or 0)
    ready = bool(manifest.get("ready"))

    return {
        "needs_update": bool(ready and latest and latest < target),
        "latest": latest,
        "target": target,
        "sessions": sessions,
        "ready": ready,
    }


def _reconcile_history_from_shards(
    ctx: dict[str, str],
    history: pd.DataFrame,
    manifest: dict[str, Any],
) -> pd.DataFrame:
    """Recover any day shard that was saved before a prior process stopped."""
    if history is None:
        history = _normalise_history(pd.DataFrame())

    have = set(history["date"]) if not history.empty else set()
    frames = [history] if not history.empty else []
    recovered = 0

    for session_date in sorted(_completed_dates(manifest)):
        if session_date in have:
            continue
        path = _day_path(ctx["user_id"], session_date)
        if not path.exists():
            _cloud_download_day(ctx, session_date, path)
        if path.exists():
            try:
                shard = _normalise_history(pd.read_parquet(path))
                if not shard.empty:
                    frames.append(shard)
                    have.add(session_date)
                    recovered += 1
            except Exception as exc:
                LOGGER.warning("History shard recovery failed %s: %s", session_date, exc)

    if not recovered:
        return history

    merged = _normalise_history(pd.concat(frames, ignore_index=True))
    history_path, _, _ = _paths(ctx["user_id"])
    merged.to_parquet(history_path, index=False, compression="zstd")
    _cloud_upload(ctx, HISTORY_NAME, history_path)
    return merged


def _persist_completed_session(
    ctx: dict[str, str],
    *,
    history: pd.DataFrame,
    session_date: date,
    day: pd.DataFrame,
    completed_dates: set[date],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Persist one successful EOD session before moving to the next."""
    clean_day = _normalise_history(day)
    if clean_day.empty:
        raise RuntimeError(f"{session_date.isoformat()} returned no usable rows.")

    # 1) Save the individual day locally first.
    day_path = _day_path(ctx["user_id"], session_date)
    clean_day.to_parquet(day_path, index=False, compression="zstd")

    # Cloud day-shard upload is attempted but does not discard a valid local day.
    cloud_day_ok = _cloud_upload_day(ctx, session_date, day_path)

    # 2) Merge into the compact local history.
    merged = _normalise_history(pd.concat([history, clean_day], ignore_index=True))
    history_path, _, _ = _paths(ctx["user_id"])
    merged.to_parquet(history_path, index=False, compression="zstd")

    # 3) Write a manifest that explicitly carries every completed date.
    completed_dates = set(completed_dates)
    completed_dates.add(session_date)
    manifest = _manifest_from_history(merged)
    manifest["completed_dates"] = [d.isoformat() for d in sorted(completed_dates)]
    manifest["last_saved_session"] = max(completed_dates).isoformat()
    # The individual day shard is already durable in cloud storage. Avoid
    # reading/uploading the entire multi-million-row compact parquet after each
    # day because that creates a large extra in-memory bytes object.
    manifest["history_cloud_synced"] = False
    manifest["last_day_cloud_synced"] = bool(cloud_day_ok)
    _save_manifest_explicit(ctx, manifest, cloud=True)

    return merged, manifest


def _history_maintenance_worker_unlocked(ctx: dict[str, str]) -> dict[str, Any]:
    """Catch EOD history up independently from the current-price Scanner."""
    key = f"history:{ctx['user_id']}"
    manifest = _restore_manifest(ctx)
    history = _load_history_explicit(ctx)
    history = _reconcile_history_from_shards(ctx, history, manifest)

    if history.empty:
        _update_job(
            key,
            running=False,
            done=True,
            error="Scanner history is unavailable.",
            stage="Completed-history maintenance unavailable",
            finished_at=_now(),
        )
        return {"updated": 0}

    existing = set(history["date"])
    completed_dates = set(_completed_dates(manifest)) | existing
    latest = max(existing)
    target = _latest_completed_market_date()

    sessions = [
        d
        for d in _market_sessions(
            ctx,
            start_date=latest + timedelta(days=1),
            end_date=target,
        )
        if d not in existing
    ]

    _update_job(
        key,
        running=True,
        done=False,
        error="",
        stage="Checking completed market sessions",
        current_latest=latest.isoformat(),
        target_date=target.isoformat(),
        missing_sessions=len(sessions),
        updated_sessions=0,
        current_date="",
        progress=0.0,
    )

    if not sessions:
        _update_job(
            key,
            running=False,
            done=True,
            error="",
            stage="Completed history is current",
            current_latest=latest.isoformat(),
            target_date=target.isoformat(),
            missing_sessions=0,
            updated_sessions=0,
            progress=1.0,
            finished_at=_now(),
        )
        return {
            "updated": 0,
            "latest": latest.isoformat(),
            "target": target.isoformat(),
        }

    updated = 0
    failures: list[str] = []
    last_call = 0.0

    for index, session_date in enumerate(sessions, 1):
        elapsed = time.monotonic() - last_call
        if last_call and elapsed < SAFE_CALL_INTERVAL_SECONDS:
            time.sleep(SAFE_CALL_INTERVAL_SECONDS - elapsed)

        _update_job(
            key,
            stage=f"Fetching completed session {session_date.isoformat()} ({index}/{len(sessions)})",
            current_date=session_date.isoformat(),
            progress=(index - 1) / max(1, len(sessions)),
        )

        try:
            day = fetch_market_day(session_date, api_key=ctx["massive_key"])
            last_call = time.monotonic()

            if day.empty:
                failures.append(f"{session_date.isoformat()}: Massive returned no rows")
                _update_job(
                    key,
                    error=failures[-1],
                    stage=f"No EOD rows returned for {session_date.isoformat()}",
                )
                continue

            history, manifest = _persist_completed_session(
                ctx,
                history=history,
                session_date=session_date,
                day=day,
                completed_dates=completed_dates,
            )
            completed_dates = set(_completed_dates(manifest))
            existing = set(history["date"])
            updated += 1
            latest = max(existing)

            _update_job(
                key,
                error="",
                stage=f"Saved completed session {session_date.isoformat()}",
                current_latest=latest.isoformat(),
                updated_sessions=updated,
                progress=index / max(1, len(sessions)),
            )
        except Exception as exc:
            last_call = time.monotonic()
            message = f"{session_date.isoformat()}: {type(exc).__name__}: {exc}"
            failures.append(message)
            LOGGER.warning("Completed-session catch-up failed: %s", message)
            _update_job(key, error=message, stage=f"Could not save {session_date.isoformat()}")
            continue

    latest_after = max(set(history["date"]))
    remaining = max(0, len(sessions) - updated)

    # A successful EOD catch-up changes technical history. Force the heavy scan
    # to rebuild on its next normal poll, but never block today's quote overlay.
    if updated:
        _, scan_path, _ = _paths(ctx["user_id"])
        try:
            if scan_path.exists():
                os.utime(scan_path, (1, 1))
        except Exception:
            pass

    final_error = " | ".join(failures[-3:])
    _update_job(
        key,
        running=False,
        done=True,
        error=final_error,
        stage=(
            f"Completed history updated through {latest_after.isoformat()}"
            if updated
            else "Completed-history catch-up needs another retry"
        ),
        current_latest=latest_after.isoformat(),
        target_date=target.isoformat(),
        missing_sessions=remaining,
        updated_sessions=updated,
        progress=1.0,
        finished_at=_now(),
    )

    return {
        "updated": updated,
        "latest": latest_after.isoformat(),
        "target": target.isoformat(),
        "failures": failures,
    }



def _history_maintenance_worker(ctx: dict[str, str]) -> dict[str, Any]:
    """Run EOD maintenance without competing with the heavy Scanner analysis."""
    with _HEAVY_WORK_LOCK:
        result = _history_maintenance_worker_unlocked(ctx)

        # Upload the compact history only ONCE after the catch-up worker has
        # finished. Day shards already protect every successful session.
        try:
            if int(result.get("updated") or 0) > 0:
                history_path, _, _ = _paths(ctx["user_id"])
                if history_path.exists():
                    synced = _cloud_upload(ctx, HISTORY_NAME, history_path)
                    manifest = _restore_manifest(ctx)
                    if manifest:
                        manifest["history_cloud_synced"] = bool(synced)
                        _save_manifest_explicit(ctx, manifest, cloud=True)
        except Exception as exc:
            LOGGER.warning("Final compact history upload skipped: %s", exc)
        return result


def ensure_history_maintenance_started(*, force: bool = False) -> dict[str, Any]:
    """Start EOD maintenance only when history is actually behind."""
    ctx = _context()
    uid = ctx["user_id"]
    key = f"history:{uid}"

    if not ctx.get("massive_key"):
        return {
            "running": False,
            "done": True,
            "error": "Massive API key not configured.",
        }

    rollover = _history_rollover_state(ctx)
    if not rollover.get("needs_update") and not force:
        return {
            "running": False,
            "done": True,
            "fresh": True,
            "current_latest": (
                rollover["latest"].isoformat()
                if rollover.get("latest")
                else None
            ),
            "target_date": rollover["target"].isoformat(),
            "sessions": rollover.get("sessions", 0),
        }

    with _LOCK:
        existing = _JOBS.get(key) or {}
        future = existing.get("future")
        if isinstance(future, Future) and not future.done():
            return job_state("history", uid)

        future = _HISTORY_EXECUTOR.submit(_history_maintenance_worker, ctx)
        _JOBS[key] = {
            "future": future,
            "running": True,
            "done": False,
            "error": "",
            "stage": "Starting completed-history catch-up",
            "current_latest": (
                rollover["latest"].isoformat()
                if rollover.get("latest")
                else None
            ),
            "target_date": rollover["target"].isoformat(),
            "progress": 0.0,
            "started_at": _now(),
        }

    return job_state("history", uid)



def _scan_worker_unlocked(
    ctx: dict[str, str],
    *,
    history_override: pd.DataFrame | None = None,
    skip_incremental: bool = False,
) -> dict[str, Any]:
    key = f"scan:{ctx['user_id']}"
    _update_job(key, stage="Loading scanner history", progress=0.03, error="", running=True, done=False)
    LOGGER.info("Scanner scan start user=%s", ctx["user_id"])
    history = _normalise_history(history_override) if history_override is not None else _load_history_explicit(ctx)
    manifest = _manifest_from_history(history)
    if not manifest.get("ready"):
        raise RuntimeError(f"Scanner history is not ready ({manifest.get('sessions', 0)}/{MINIMUM_READY_SESSIONS} sessions).")

    if not skip_incremental:
        try:
            ensure_history_maintenance_started(force=False)
        except Exception as exc:
            LOGGER.info("EOD maintenance start skipped: %s", exc)

    _update_job(key, stage="Ranking stored history before the live overlay", progress=0.12)
    from scanner_v2 import rank_universe, _live_adjusted_ranking, SCAN_LIMIT
    _historical_pool, broad_rank, broad_diag = rank_universe(history, 1500)

    # Historical ranking is context only. Refresh every strategy-eligible stock
    # with the current IEX price so today's move can promote a symbol that was
    # not in yesterday's historical top 1,500.
    eligible_symbols = broad_rank["Symbol"].astype(str).tolist()
    _update_job(
        key,
        stage=f"Refreshing current prices across {len(eligible_symbols):,} eligible stocks",
        progress=0.20,
    )
    iex_snapshots = _fetch_alpaca_live_snapshots(ctx, eligible_symbols, feed="iex")

    current_rank = _live_adjusted_ranking(
        broad_rank,
        iex_snapshots,
        eligible_symbols,
        SCAN_LIMIT,
    )
    current_symbols = current_rank["Symbol"].astype(str).tolist()

    # Add broader consolidated session context for the actual finalists. The
    # delayed SIP feed is about 15 minutes delayed on free Alpaca accounts, but
    # it gives much better OHLC/volume coverage than IEX alone.
    _update_job(
        key,
        stage=f"Refreshing consolidated session data for {len(current_symbols):,} finalists",
        progress=0.32,
    )
    delayed_snapshots = _fetch_alpaca_live_snapshots(
        ctx,
        current_symbols,
        feed="delayed_sip",
    )
    live_snapshots = _merge_current_snapshots(
        iex_snapshots,
        delayed_snapshots,
        current_symbols,
    )

    results = run_scan_v2(
        history=history,
        live_snapshots=live_snapshots,
        candidate_pool=current_symbols,
        ranking_override=broad_rank,
        diagnostics_override=broad_diag,
        progress_callback=lambda stage, pct: _update_job(key, stage=stage, progress=pct),
    )
    _, scan_path, _ = _paths(ctx["user_id"])
    results.to_parquet(scan_path, index=False, compression="zstd")
    _cloud_upload(ctx, SCAN_NAME, scan_path)
    _update_job(key, stage="Current candidates ready", progress=1.0, done=True, running=False, rows=int(len(results)), finished_at=_now(), error="")
    LOGGER.info("Scanner scan complete rows=%s", len(results))
    return {"rows": int(len(results)), "path": str(scan_path)}



def _scan_worker(
    ctx: dict[str, str],
    *,
    history_override: pd.DataFrame | None = None,
    skip_incremental: bool = False,
) -> dict[str, Any]:
    """Heavy V2 analysis is serialized with EOD compaction to protect RAM.

    The lightweight current-price overlay does not use this lock, so displayed
    prices can continue refreshing even while history maintenance is waiting.
    """
    with _HEAVY_WORK_LOCK:
        return _scan_worker_unlocked(
            ctx,
            history_override=history_override,
            skip_incremental=skip_incremental,
        )


def ensure_scan_started(*, force: bool = False) -> dict[str, Any]:
    ctx = _context()
    uid = ctx["user_id"]
    manifest = _restore_manifest(ctx)
    if manifest and not local_manifest(uid):
        _save_manifest_explicit(ctx, manifest, cloud=False)
    if not manifest.get("ready"):
        ensure_bootstrap_started()
        return {"running": False, "waiting_for_history": True, "stage": "Building Scanner v2 history in the background"}
    key = f"scan:{uid}"
    with _LOCK:
        existing = _JOBS.get(key) or {}
        future = existing.get("future")
        if isinstance(future, Future) and not future.done():
            return job_state("scan", uid)
        if not force and latest_scan_is_fresh(uid, ttl_minutes=LIVE_SCAN_TTL_MINUTES):
            return {"running": False, "fresh": True, "done": True}
        future = _EXECUTOR.submit(_scan_worker, ctx)
        _JOBS[key] = {"future": future, "running": True, "stage": "Starting current market scan", "progress": 0.01, "started_at": _now()}
    return job_state("scan", uid)


def load_latest_scan_results(user_id: str | None = None) -> pd.DataFrame:
    uid = str(user_id or current_user_id() or "anonymous")
    _, scan_path, _ = _paths(uid)
    if not scan_path.exists():
        ctx = _context()
        if ctx["user_id"] == uid:
            _cloud_download(ctx, SCAN_NAME, scan_path)
    if not scan_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(scan_path)
    except Exception:
        return pd.DataFrame()


def latest_scan_timestamp(user_id: str | None = None) -> float | None:
    uid = str(user_id or current_user_id() or "anonymous")
    _, scan_path, _ = _paths(uid)
    if not scan_path.exists():
        return None
    try:
        return scan_path.stat().st_mtime
    except Exception:
        return None


def latest_scan_is_fresh(user_id: str | None = None, *, ttl_minutes: int = 30) -> bool:
    """A scan is fresh only when a recent, readable, non-empty result exists.

    A freshly downloaded/rewritten empty parquet must never suppress the first
    real Scanner v2 run.  This was the cause of the 220/220 + no-results state.
    """
    uid = str(user_id or current_user_id() or "anonymous")
    stamp = latest_scan_timestamp(uid)
    if not stamp or time.time() - stamp >= max(1, int(ttl_minutes)) * 60:
        return False
    results = load_latest_scan_results(uid)
    return bool(results is not None and not results.empty and "Symbol" in results.columns)


def scanner_status_text() -> str:
    uid = str(current_user_id() or "anonymous")
    scan = job_state("scan", uid)
    bootstrap = job_state("bootstrap", uid)
    manifest = local_manifest(uid)
    if scan.get("running"):
        return str(scan.get("stage") or "Refreshing scanner")
    if not manifest.get("ready"):
        sessions = int(manifest.get("sessions") or bootstrap.get("progress") or 0)
        last_saved = manifest.get("last_saved_session") or bootstrap.get("last_saved_session")
        suffix = f" · last saved {last_saved}" if last_saved else ""
        return f"Building market history ({sessions}/{MINIMUM_READY_SESSIONS} durable sessions){suffix}"
    if latest_scan_is_fresh(uid, ttl_minutes=LIVE_SCAN_TTL_MINUTES):
        return "Current scanner candidates are fresh"
    return "Scanner candidates will refresh automatically"


def _fetch_alpaca_live_snapshots(
    ctx: dict[str, str],
    symbols: list[str],
    *,
    feed: str = "iex",
) -> dict[str, dict[str, Any]]:
    """Fetch current-session snapshots in bounded Alpaca batches."""
    key = ctx.get("alpaca_key") or ""
    secret = ctx.get("alpaca_secret") or ""
    if not key or not secret or not symbols:
        return {}

    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    out: dict[str, dict[str, Any]] = {}
    batch_size = 250

    for offset in range(0, len(symbols), batch_size):
        batch = symbols[offset: offset + batch_size]
        try:
            response = requests.get(
                "https://data.alpaca.markets/v2/stocks/snapshots",
                headers=headers,
                params={"symbols": ",".join(batch), "feed": feed},
                timeout=(5, 20),
            )
            if response.status_code == 429:
                time.sleep(1.25)
                continue
            if response.status_code in {401, 403} and feed == "delayed_sip":
                LOGGER.info("Alpaca delayed SIP unavailable (%s); using IEX-only fallback.", response.status_code)
                return {}
            response.raise_for_status()
            payload = response.json()
            snapshots = (
                payload.get("snapshots")
                if isinstance(payload, dict) and isinstance(payload.get("snapshots"), dict)
                else payload
            )
            if not isinstance(snapshots, dict):
                continue

            for symbol, snap in snapshots.items():
                if not isinstance(snap, dict):
                    continue
                daily = snap.get("dailyBar") or snap.get("daily_bar") or {}
                minute = snap.get("minuteBar") or snap.get("minute_bar") or {}
                latest = snap.get("latestTrade") or snap.get("latest_trade") or {}

                trade_price = latest.get("p") if isinstance(latest, dict) else None
                minute_close = minute.get("c") if isinstance(minute, dict) else None
                daily_close = daily.get("c") if isinstance(daily, dict) else None
                close = trade_price if trade_price is not None else (minute_close if minute_close is not None else daily_close)
                if close is None:
                    continue

                asof = None
                for candidate in (
                    latest.get("t") if isinstance(latest, dict) else None,
                    minute.get("t") if isinstance(minute, dict) else None,
                    daily.get("t") if isinstance(daily, dict) else None,
                ):
                    if candidate:
                        asof = candidate
                        break

                out[str(symbol).upper()] = {
                    "open": daily.get("o") if isinstance(daily, dict) else close,
                    "high": daily.get("h") if isinstance(daily, dict) else close,
                    "low": daily.get("l") if isinstance(daily, dict) else close,
                    "close": close,
                    "volume": daily.get("v") if isinstance(daily, dict) else None,
                    "asof": asof,
                    "feed": feed,
                }
        except Exception as exc:
            LOGGER.debug("Alpaca %s snapshot batch failed: %s", feed, exc)
            continue
    return out



def refresh_current_prices_for_scan(
    frame: pd.DataFrame,
    *,
    max_age_seconds: int = LIVE_PRICE_TTL_SECONDS,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Overlay freshest available prices onto an already-computed Scanner table.

    This is intentionally lightweight: it does NOT rerun the expensive 500-stock
    analysis. It only refreshes the trader-facing current price and its age.
    """
    if frame is None or frame.empty or "Symbol" not in frame.columns:
        return frame, {"updated": 0, "asof": None, "stale": True}

    ctx = _context()
    symbols = frame["Symbol"].astype(str).str.upper().tolist()
    cache_key = f"liveprice:{ctx['user_id']}"

    with _LOCK:
        existing = _JOBS.get(cache_key) or {}
        cached_frame = existing.get("frame")
        fetched_at = float(existing.get("fetched_at") or 0.0)
        if (
            isinstance(cached_frame, pd.DataFrame)
            and not cached_frame.empty
            and time.time() - fetched_at <= max_age_seconds
        ):
            return cached_frame.copy(), {
                "updated": int(existing.get("updated") or 0),
                "asof": existing.get("asof"),
                "stale": False,
                "source": existing.get("source") or "Alpaca IEX",
            }

    snapshots = _fetch_alpaca_live_snapshots(ctx, symbols, feed="iex")
    refreshed = frame.copy()
    asof_values: list[str] = []
    updated = 0

    for idx, symbol in refreshed["Symbol"].astype(str).str.upper().items():
        snap = snapshots.get(symbol) or {}
        price = snap.get("close")
        if price is None:
            continue
        updated += 1
        if "Close" in refreshed.columns:
            refreshed.at[idx, "Close"] = price
        if "Current Price" in refreshed.columns:
            refreshed.at[idx, "Current Price"] = price
        asof = snap.get("asof")
        if asof:
            asof_values.append(str(asof))

    latest_asof = max(asof_values) if asof_values else None
    source = "Alpaca IEX real-time"

    with _LOCK:
        _JOBS[cache_key] = {
            "frame": refreshed.copy(),
            "fetched_at": time.time(),
            "updated": updated,
            "asof": latest_asof,
            "source": source,
        }

    return refreshed, {
        "updated": updated,
        "asof": latest_asof,
        "stale": updated == 0,
        "source": source,
    }


def clear_current_price_cache() -> None:
    try:
        ctx = _context()
        with _LOCK:
            _JOBS.pop(f"liveprice:{ctx['user_id']}", None)
    except Exception:
        pass


def _merge_current_snapshots(
    iex: dict[str, dict[str, Any]],
    delayed_sip: dict[str, dict[str, Any]],
    symbols: list[str],
) -> dict[str, dict[str, Any]]:
    """Real-time IEX price + delayed consolidated SIP OHLC/volume."""
    merged: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        ticker = str(symbol).upper()
        live = dict(iex.get(ticker) or {})
        delayed = dict(delayed_sip.get(ticker) or {})
        current_price = live.get("close")
        if current_price is None:
            current_price = delayed.get("close")
        if current_price is None:
            continue

        context = delayed if delayed else live
        open_price = context.get("open")
        high = context.get("high")
        low = context.get("low")
        try:
            high = max(float(high), float(current_price)) if high is not None else float(current_price)
        except Exception:
            high = current_price
        try:
            low = min(float(low), float(current_price)) if low is not None else float(current_price)
        except Exception:
            low = current_price

        merged[ticker] = {
            "open": open_price if open_price is not None else current_price,
            "high": high,
            "low": low,
            "close": current_price,
            "volume": delayed.get("volume") if delayed else None,
            "asof": live.get("asof") or delayed.get("asof"),
            "volume_asof": delayed.get("asof") if delayed else None,
            "price_feed": "Alpaca IEX real-time" if live else "Alpaca delayed SIP",
            "volume_feed": "Alpaca delayed SIP (~15m)" if delayed and delayed.get("volume") is not None else "Completed-day baseline",
        }
    return merged

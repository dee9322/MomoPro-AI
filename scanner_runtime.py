from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
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

# Scanner v2 gets its own worker. It must never run inside MomoPro's generic
# automatic-loading fragment because a whole-market job can take long enough to
# block unrelated pages. The worker only touches plain Python state, local files,
# HTTP endpoints and an explicitly authenticated Supabase client.
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="momopro-scanner-v2")
_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}

BASE_DIR = Path(os.getenv("MOMOPRO_SCANNER_CACHE", "/tmp/momopro_scanner_v2"))
HISTORY_NAME = "massive_daily_history.parquet"
SCAN_NAME = "latest_scan.parquet"
MANIFEST_NAME = "scanner_manifest.json"
STORAGE_BUCKET = "scanner-data"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_user(user_id: str | None) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(user_id or "anonymous"))


def _paths(user_id: str | None) -> tuple[Path, Path, Path]:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    prefix = _safe_user(user_id)
    return (
        BASE_DIR / f"{prefix}_{HISTORY_NAME}",
        BASE_DIR / f"{prefix}_{SCAN_NAME}",
        BASE_DIR / f"{prefix}_{MANIFEST_NAME}",
    )


def _cloud_object(user_id: str, filename: str) -> str:
    return f"{user_id}/{filename}"


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


def _manifest_from_history(history: pd.DataFrame) -> dict[str, Any]:
    if history is None or history.empty:
        return {"sessions": 0, "symbols": 0, "rows": 0, "ready": False, "latest": None, "target": TARGET_SESSIONS}
    dates = pd.to_datetime(history["date"], errors="coerce").dropna()
    sessions = int(dates.dt.date.nunique())
    latest = dates.max().date().isoformat() if not dates.empty else None
    return {
        "sessions": sessions,
        "symbols": int(history["symbol"].nunique()),
        "rows": int(len(history)),
        "ready": sessions >= MINIMUM_READY_SESSIONS,
        "latest": latest,
        "target": TARGET_SESSIONS,
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
            destination.write_bytes(payload)
            return True
    except Exception:
        return False
    return False


def _cloud_upload(ctx: dict[str, str], filename: str, source: Path) -> bool:
    client = _make_cloud_client(ctx)
    if client is None or not source.exists():
        return False
    try:
        bucket = client.storage.from_(STORAGE_BUCKET)
        data = source.read_bytes()
        options = {"content-type": "application/octet-stream", "upsert": "true"}
        try:
            bucket.upload(_cloud_object(ctx["user_id"], filename), data, options)
        except Exception:
            bucket.update(_cloud_object(ctx["user_id"], filename), data, options)
        return True
    except Exception:
        return False


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
    return out.dropna(subset=["date", "symbol", "close"]).drop_duplicates(["date", "symbol"], keep="last")[expected].sort_values(["symbol", "date"]).reset_index(drop=True)


def _load_history_explicit(ctx: dict[str, str]) -> pd.DataFrame:
    history_path, _, _ = _paths(ctx["user_id"])
    if not history_path.exists():
        _cloud_download(ctx, HISTORY_NAME, history_path)
    if not history_path.exists():
        return _normalise_history(pd.DataFrame())
    try:
        return _normalise_history(pd.read_parquet(history_path))
    except Exception:
        history_path.unlink(missing_ok=True)
        return _normalise_history(pd.DataFrame())


def _save_history_explicit(ctx: dict[str, str], history: pd.DataFrame, *, cloud: bool) -> dict[str, Any]:
    history_path, _, _ = _paths(ctx["user_id"])
    history = _normalise_history(history)
    history.to_parquet(history_path, index=False, compression="zstd")
    manifest = _manifest_from_history(history)
    _write_manifest(ctx["user_id"], manifest)
    if cloud:
        _cloud_upload(ctx, HISTORY_NAME, history_path)
        _, _, manifest_path = _paths(ctx["user_id"])
        _cloud_upload(ctx, MANIFEST_NAME, manifest_path)
    return manifest


def _candidate_dates(existing: set[Any], target: int) -> list[Any]:
    from datetime import timedelta
    cursor = datetime.now(timezone.utc).date() - timedelta(days=1)
    dates = []
    # Overscan modestly for market holidays.
    while len(existing) + len(dates) < target and len(dates) < target * 2:
        if cursor.weekday() < 5 and cursor not in existing:
            dates.append(cursor)
        cursor -= timedelta(days=1)
    return dates


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
            state.pop("future", None)
        return state


def _bootstrap_worker(ctx: dict[str, str]) -> dict[str, Any]:
    key = f"bootstrap:{ctx['user_id']}"
    history = _load_history_explicit(ctx)
    manifest = _manifest_from_history(history)
    existing = set(history["date"]) if not history.empty else set()
    dates = _candidate_dates(existing, TARGET_SESSIONS)
    _update_job(key, stage="Downloading consolidated daily market history", progress=manifest.get("sessions", 0), total=TARGET_SESSIONS, error="")

    last_call = 0.0
    successful_since_cloud = 0
    for session_date in dates:
        if manifest.get("sessions", 0) >= TARGET_SESSIONS:
            break
        elapsed = time.monotonic() - last_call
        if last_call and elapsed < SAFE_CALL_INTERVAL_SECONDS:
            time.sleep(SAFE_CALL_INTERVAL_SECONDS - elapsed)
        try:
            day = fetch_market_day(session_date, api_key=ctx["massive_key"])
            last_call = time.monotonic()
            if not day.empty:
                history = _normalise_history(pd.concat([history, day], ignore_index=True))
                manifest = _save_history_explicit(ctx, history, cloud=False)
                successful_since_cloud += 1
                if successful_since_cloud >= 10:
                    _save_history_explicit(ctx, history, cloud=True)
                    successful_since_cloud = 0
            _update_job(
                key,
                stage="Downloading consolidated daily market history",
                progress=manifest.get("sessions", 0),
                total=TARGET_SESSIONS,
                current_date=session_date.isoformat(),
                ready=bool(manifest.get("ready")),
            )
        except Exception as exc:
            last_call = time.monotonic()
            msg = str(exc)
            _update_job(key, error=msg, current_date=session_date.isoformat())
            # A 429 should never cause a tight retry loop. Pause a full window.
            if "429" in msg or "rate limit" in msg.lower():
                time.sleep(61)
            else:
                time.sleep(2)

    manifest = _save_history_explicit(ctx, history, cloud=True)
    _update_job(key, stage="History ready" if manifest.get("ready") else "History paused", progress=manifest.get("sessions", 0), total=TARGET_SESSIONS, ready=bool(manifest.get("ready")), done=True)
    return manifest


def ensure_bootstrap_started() -> dict[str, Any]:
    ctx = _context()
    uid = ctx["user_id"]
    key = f"bootstrap:{uid}"
    if not ctx.get("massive_key"):
        return {"running": False, "error": "Massive API key not configured."}
    manifest = local_manifest(uid)
    if manifest.get("ready"):
        return {**manifest, "running": False, "done": True}
    with _LOCK:
        existing = _JOBS.get(key) or {}
        future = existing.get("future")
        if isinstance(future, Future) and not future.done():
            return job_state("bootstrap", uid)
        future = _EXECUTOR.submit(_bootstrap_worker, ctx)
        _JOBS[key] = {"future": future, "running": True, "stage": "Starting Scanner v2 history", "progress": int(manifest.get("sessions") or 0), "total": TARGET_SESSIONS, "started_at": _now()}
    return job_state("bootstrap", uid)


def _scan_worker(ctx: dict[str, str]) -> dict[str, Any]:
    key = f"scan:{ctx['user_id']}"
    _update_job(key, stage="Loading scanner history", progress=0.05, error="")
    history = _load_history_explicit(ctx)
    manifest = _manifest_from_history(history)
    if not manifest.get("ready"):
        raise RuntimeError(f"Scanner history is not ready ({manifest.get('sessions', 0)}/{MINIMUM_READY_SESSIONS} sessions).")

    _update_job(key, stage="Building the strategy-aware current-session pool", progress=0.15)
    # Massive Basic supplies consolidated EOD history. We first produce a broad
    # strategy-aware pool locally, then overlay current Alpaca IEX prices on that
    # bounded pool so today's EMA/reclaim/location changes can affect selection
    # without trusting incomplete IEX volume as the liquidity source.
    from scanner_v2 import rank_universe
    broad_symbols, _broad_rank, _diag = rank_universe(history, 1500)
    _update_job(key, stage=f"Refreshing current prices for {len(broad_symbols)} strategy-relevant stocks", progress=0.25)
    live_snapshots = _fetch_alpaca_live_snapshots(ctx, broad_symbols)
    results = run_scan_v2(
        history=history,
        live_snapshots=live_snapshots,
        candidate_pool=broad_symbols,
        progress_callback=lambda stage, pct: _update_job(key, stage=stage, progress=pct),
    )
    _, scan_path, _ = _paths(ctx["user_id"])
    results.to_parquet(scan_path, index=False, compression="zstd")
    _cloud_upload(ctx, SCAN_NAME, scan_path)
    _update_job(key, stage="Current candidates ready", progress=1.0, done=True, rows=int(len(results)), finished_at=_now())
    return {"rows": int(len(results)), "path": str(scan_path)}


def ensure_scan_started(*, force: bool = False) -> dict[str, Any]:
    ctx = _context()
    uid = ctx["user_id"]
    manifest = local_manifest(uid)
    if not manifest.get("ready"):
        ensure_bootstrap_started()
        return {"running": False, "waiting_for_history": True, "stage": "Building Scanner v2 history in the background"}
    key = f"scan:{uid}"
    with _LOCK:
        existing = _JOBS.get(key) or {}
        future = existing.get("future")
        if isinstance(future, Future) and not future.done():
            return job_state("scan", uid)
        if not force and latest_scan_is_fresh(uid, ttl_minutes=30):
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
    stamp = latest_scan_timestamp(user_id)
    return bool(stamp and time.time() - stamp < max(1, int(ttl_minutes)) * 60)


def scanner_status_text() -> str:
    uid = str(current_user_id() or "anonymous")
    scan = job_state("scan", uid)
    bootstrap = job_state("bootstrap", uid)
    manifest = local_manifest(uid)
    if scan.get("running"):
        return str(scan.get("stage") or "Refreshing scanner")
    if not manifest.get("ready"):
        sessions = int(manifest.get("sessions") or bootstrap.get("progress") or 0)
        return f"Building market history in background ({sessions}/{MINIMUM_READY_SESSIONS}+ sessions needed)"
    if latest_scan_is_fresh(uid, ttl_minutes=30):
        return "Current scanner candidates are fresh"
    return "Scanner candidates will refresh automatically"


def _fetch_alpaca_live_snapshots(ctx: dict[str, str], symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch lightweight current-session snapshots for a bounded strategy pool.

    Massive Basic is end-of-day. Alpaca's free IEX snapshot is used only as a
    current-price overlay; consolidated historical volume remains the source for
    liquidity/RVOL so incomplete IEX volume cannot eliminate quieter setups.
    """
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
                params={"symbols": ",".join(batch), "feed": "iex"},
                timeout=(5, 20),
            )
            if response.status_code == 429:
                time.sleep(1.5)
                continue
            response.raise_for_status()
            payload = response.json()
            snapshots = payload.get("snapshots") if isinstance(payload, dict) and isinstance(payload.get("snapshots"), dict) else payload
            if not isinstance(snapshots, dict):
                continue
            for symbol, snap in snapshots.items():
                if not isinstance(snap, dict):
                    continue
                daily = snap.get("dailyBar") or snap.get("daily_bar") or {}
                latest = snap.get("latestTrade") or snap.get("latest_trade") or {}
                close = daily.get("c") if isinstance(daily, dict) else None
                if close is None and isinstance(latest, dict):
                    close = latest.get("p")
                if close is None:
                    continue
                out[str(symbol).upper()] = {
                    "open": daily.get("o") if isinstance(daily, dict) else close,
                    "high": daily.get("h") if isinstance(daily, dict) else close,
                    "low": daily.get("l") if isinstance(daily, dict) else close,
                    "close": close,
                    "iex_volume": daily.get("v") if isinstance(daily, dict) else None,
                }
        except Exception:
            continue
    return out

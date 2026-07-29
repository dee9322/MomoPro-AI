"""Central settings access and runtime helpers for MomoPro AI."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from settings_storage import load_settings, reset_settings, save_settings
from account_context import AccountContext, context_from_saved, resolve_webull_snapshot


def get_settings() -> Dict[str, Any]:
    return load_settings()


def get_setting(path: str, default: Any = None, settings: Dict[str, Any] | None = None) -> Any:
    current: Any = settings or load_settings()
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def update_section(section: str, values: Dict[str, Any]) -> Dict[str, Any]:
    settings = load_settings()
    existing = settings.get(section, {})
    if not isinstance(existing, dict):
        existing = {}
    existing.update(deepcopy(values))
    settings[section] = existing
    return save_settings(settings)



def refresh_broker_account_context(snapshot: Dict[str, Any] | None = None) -> AccountContext:
    """Resolve and persist the current Webull account context when valid."""
    if snapshot is None:
        try:
            from webull_sync import load_webull_snapshot
            snapshot = load_webull_snapshot()
        except Exception:
            snapshot = {}
    live = resolve_webull_snapshot(snapshot)
    if live.account_value > 0:
        settings = load_settings()
        settings["broker"] = live.to_dict()
        save_settings(settings)
    return live


def get_account_context(settings: Dict[str, Any] | None = None, *, refresh: bool = True) -> AccountContext:
    """Return one canonical broker account context for every app feature.

    A valid live Webull snapshot wins. If a transient API/cloud read is empty, the
    last known Webull value saved in settings is retained instead of reverting the
    entire app to the $10,000 manual planning fallback.
    """
    s = settings or load_settings()
    if refresh:
        live = refresh_broker_account_context()
        if live.account_value > 0:
            return live
    return context_from_saved(s.get("broker"))


def get_effective_account_size(settings: Dict[str, Any] | None = None, *, refresh: bool = True) -> tuple[float, str]:
    s = settings or load_settings()
    context = get_account_context(s, refresh=refresh)
    if context.account_value > 0:
        source = context.source if context.is_live else f"{context.source} (last synced)"
        return context.account_value, source
    return float(get_setting("risk.account_size", 10000.0, s) or 0.0), "Manual fallback"


def settings_summary(settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    s = settings or load_settings()
    return {
        "Trading style": get_setting("profile.trading_style", "—", s),
        "Account size": get_setting("risk.account_size", 0, s),
        "Risk / trade": get_setting("risk.risk_per_trade_pct", 0, s),
        "Scanner price range": f"${get_setting('scanner.price_min', 0, s):g}–${get_setting('scanner.price_max', 0, s):g}",
        "Minimum RVOL": get_setting("scanner.minimum_rvol", 0, s),
        "Minimum ATR %": get_setting("scanner.minimum_atr_pct", 0, s),
        "AI style": get_setting("ai.analysis_style", "—", s),
        "Dashboard universe": get_setting("dashboard.default_universe", "Entire Market", s),
        "Broker": get_setting("journal.default_broker", "—", s),
    }

__all__ = ["get_settings", "get_setting", "update_section", "save_settings", "reset_settings", "settings_summary", "refresh_broker_account_context", "get_account_context", "get_effective_account_size"]

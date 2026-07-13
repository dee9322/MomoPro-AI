"""Central settings access and runtime helpers for MomoPro AI."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from settings_storage import load_settings, reset_settings, save_settings


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

__all__ = ["get_settings", "get_setting", "update_section", "save_settings", "reset_settings", "settings_summary"]

"""Typed defaults and validation helpers for MomoPro AI settings."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

SETTINGS_VERSION = "0.92"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "version": SETTINGS_VERSION,
    "profile": {
        "display_name": "Dee",
        "trading_style": "Swing Trading",
        "typical_hold_days": 10,
        "preferred_setups": ["EMA21 Reclaim", "EMA21 Retest", "Higher-Low Continuation", "Bull Flag"],
        "preferred_sectors": [],
        "preferred_universes": ["Entire Market"],
    },
    "risk": {
        "account_size": 10000.0,
        "risk_per_trade_pct": 1.0,
        "max_position_pct": 25.0,
        "max_open_positions": 5,
        "daily_loss_limit_pct": 2.0,
        "weekly_loss_limit_pct": 5.0,
        "minimum_rr": 2.0,
        "stop_style": "Structure / Support",
        "partial_profit_style": "Scale at T1 / T2 / T3",
    },
    "scanner": {
        "price_min": 3.0,
        "price_max": 50.0,
        "minimum_average_volume": 1000000,
        "minimum_rvol": 1.1,
        "minimum_atr_pct": 4.0,
        "maximum_ema21_extension_pct": 6.0,
        "minimum_momo_score": 0,
        "minimum_grade": "C",
        "result_limit": 100,
        "default_universe": "Entire Market",
        "exclude_etfs": True,
        "exclude_otc": True,
    },
    "indicators": {
        "ema_fast": 21,
        "ema_mid": 50,
        "ema_slow": 200,
        "rsi_length": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "atr_length": 14,
        "rvol_lookback": 20,
        "primary_timeframe": "Daily",
        "confirmation_timeframes": ["4H", "1H", "15m"],
    },
    "ai": {
        "analysis_style": "Balanced",
        "response_depth": "Detailed",
        "challenge_thesis": True,
        "technical_weight": 35,
        "market_weight": 15,
        "news_weight": 20,
        "smart_money_weight": 15,
        "historical_weight": 15,
        "buy_threshold": 85,
        "watch_threshold": 70,
        "wait_threshold": 50,
    },
    "dashboard": {
        "default_universe": "Entire Market",
        "candidate_count": 10,
        "show_market_health": True,
        "show_sector_leadership": True,
        "show_scanner_candidates": True,
        "show_watchlist_alerts": True,
        "show_open_trades": True,
        "show_market_news": True,
        "show_ai_recommendations": True,
        "show_broker_status": True,
        "morning_brief_enabled": True,
    },
    "journal": {
        "default_direction": "Long",
        "default_source": "Manual",
        "require_entry_thesis": True,
        "require_exit_review": True,
        "save_chart_screenshots": True,
        "default_broker": "Webull",
    },
    "performance": {
        "default_source_filter": "All Trades",
        "default_period": "All Time",
        "pnl_display": "Net P/L",
        "show_fees": True,
        "show_equity_curve": True,
        "show_ai_accuracy": True,
        "show_discipline_metrics": True,
    },
    "alerts": {
        "default_cooldown_hours": 24,
        "minimum_priority": "Medium",
        "morning_brief_alert_summary": True,
        "quiet_hours_enabled": False,
        "quiet_hours_start": "21:00",
        "quiet_hours_end": "06:00",
    },
    "data": {
        "market_cache_minutes": 15,
        "news_cache_minutes": 15,
        "scanner_cache_minutes": 30,
        "auto_refresh_dashboard": False,
        "webull_csv_enabled": True,
        "webull_api_mode": "Not Connected",
        "tradingview_status": "Planned for v0.95",
    },
}


def merge_defaults(value: Dict[str, Any] | None) -> Dict[str, Any]:
    """Merge persisted settings with defaults, preserving future-compatible keys."""
    result = deepcopy(DEFAULT_SETTINGS)
    if not isinstance(value, dict):
        return result
    for section, section_value in value.items():
        if section in result and isinstance(result[section], dict) and isinstance(section_value, dict):
            result[section].update(section_value)
        else:
            result[section] = section_value
    result["version"] = SETTINGS_VERSION
    return validate_settings(result)


def validate_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Apply safety bounds without silently changing user intent beyond valid ranges."""
    s = deepcopy(settings)
    risk = s["risk"]
    risk["account_size"] = max(float(risk.get("account_size", 0)), 0.0)
    risk["risk_per_trade_pct"] = min(max(float(risk.get("risk_per_trade_pct", 1)), 0.0), 100.0)
    risk["max_position_pct"] = min(max(float(risk.get("max_position_pct", 25)), 0.0), 100.0)
    risk["max_open_positions"] = max(int(risk.get("max_open_positions", 1)), 1)
    risk["minimum_rr"] = max(float(risk.get("minimum_rr", 0)), 0.0)

    scan = s["scanner"]
    scan["price_min"] = max(float(scan.get("price_min", 0)), 0.0)
    scan["price_max"] = max(float(scan.get("price_max", scan["price_min"])), scan["price_min"])
    scan["minimum_average_volume"] = max(int(scan.get("minimum_average_volume", 0)), 0)
    scan["minimum_rvol"] = max(float(scan.get("minimum_rvol", 0)), 0.0)
    scan["minimum_atr_pct"] = max(float(scan.get("minimum_atr_pct", 0)), 0.0)
    scan["maximum_ema21_extension_pct"] = max(float(scan.get("maximum_ema21_extension_pct", 0)), 0.0)
    scan["result_limit"] = min(max(int(scan.get("result_limit", 100)), 1), 1000)

    ai = s["ai"]
    for key in ("technical_weight", "market_weight", "news_weight", "smart_money_weight", "historical_weight"):
        ai[key] = min(max(int(ai.get(key, 0)), 0), 100)
    for key in ("buy_threshold", "watch_threshold", "wait_threshold"):
        ai[key] = min(max(int(ai.get(key, 0)), 0), 100)
    return s

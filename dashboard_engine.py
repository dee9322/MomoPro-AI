from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from alert_engine import load_alerts
from watchlist_manager import get_symbols, list_watchlists

TRADE_DATA_FILE = Path(__file__).with_name("trade_data.json")

UNIVERSE_OPTIONS = [
    "Entire Market",
    "Watchlist",
    "Top Gainers",
    "Recent IPOs",
    "AI Stocks",
    "Biotech",
    "Semiconductors",
]


def _valid(value: Any) -> bool:
    if value is None:
        return False
    try:
        return not pd.isna(value)
    except Exception:
        return True


def _first_present(row: pd.Series | dict[str, Any], names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        try:
            value = row.get(name)
        except Exception:
            continue
        if _valid(value):
            return value
    return default


def _numeric_series(df: pd.DataFrame, names: Iterable[str]) -> pd.Series | None:
    for name in names:
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce")
    return None


def _text_series(df: pd.DataFrame, names: Iterable[str]) -> pd.Series:
    values = pd.Series("", index=df.index, dtype="object")
    for name in names:
        if name in df.columns:
            values = values + " " + df[name].fillna("").astype(str)
    return values.str.lower()


def filter_scan_universe(
    scan_df: pd.DataFrame | None,
    universe: str,
    active_watchlist: str | None = None,
) -> tuple[pd.DataFrame, str | None]:
    if scan_df is None or scan_df.empty:
        return pd.DataFrame(), "Run the Scanner to populate dashboard candidates."

    filtered = scan_df.copy()
    universe = universe if universe in UNIVERSE_OPTIONS else "Entire Market"

    if universe == "Watchlist":
        names = list_watchlists()
        selected = active_watchlist if active_watchlist in names else (names[0] if names else None)
        symbols = set(get_symbols(selected)) if selected else set()
        if "Symbol" not in filtered.columns:
            return filtered.iloc[0:0], "Scanner results do not include a Symbol column."
        filtered = filtered[filtered["Symbol"].astype(str).str.upper().isin(symbols)]
        if not symbols:
            return filtered, "The selected watchlist has no symbols yet."

    elif universe == "Top Gainers":
        change = _numeric_series(filtered, ["Day %", "Change %", "Today %", "Return 1D %", "Daily Change %"])
        if change is None:
            return filtered, "A daily-change field is unavailable, so the standard scanner ranking is shown."
        filtered = filtered.assign(_dashboard_change=change).sort_values("_dashboard_change", ascending=False)

    elif universe == "Recent IPOs":
        text = _text_series(filtered, ["Tags", "Category", "Theme", "Setup", "Company", "Industry"])
        mask = text.str.contains(r"\bipo\b|recent ipo|new issue", regex=True)
        if mask.any():
            filtered = filtered[mask]
        else:
            return filtered.iloc[0:0], "Recent-IPO metadata is not available in the current scan results."

    elif universe == "AI Stocks":
        text = _text_series(filtered, ["Company", "Sector", "Industry", "Tags", "Theme", "Reasons"])
        mask = text.str.contains(r"artificial intelligence|\bai\b|machine learning|data center|cloud", regex=True)
        if mask.any():
            filtered = filtered[mask]
        else:
            return filtered.iloc[0:0], "AI-theme metadata is not available in the current scan results."

    elif universe == "Biotech":
        text = _text_series(filtered, ["Company", "Sector", "Industry", "Tags", "Theme"])
        mask = text.str.contains(r"biotech|biotechnology|pharma|pharmaceutical|therapeutic", regex=True)
        if mask.any():
            filtered = filtered[mask]
        else:
            return filtered.iloc[0:0], "Biotech metadata is not available in the current scan results."

    elif universe == "Semiconductors":
        text = _text_series(filtered, ["Company", "Sector", "Industry", "Tags", "Theme"])
        mask = text.str.contains(r"semiconductor|chip|foundry|integrated circuit", regex=True)
        if mask.any():
            filtered = filtered[mask]
        else:
            return filtered.iloc[0:0], "Semiconductor metadata is not available in the current scan results."

    return filtered, None


def rank_scanner_candidates(scan_df: pd.DataFrame | None, limit: int = 10) -> list[dict[str, Any]]:
    if scan_df is None or scan_df.empty:
        return []

    df = scan_df.copy()
    score = _numeric_series(df, ["Momo Score", "Score"])
    confidence = _numeric_series(df, ["Momo Confidence", "Confidence %", "Confidence"])
    opportunity = _numeric_series(df, ["Opportunity", "Opportunity Score"])

    rank_value = pd.Series(0.0, index=df.index)
    if score is not None:
        rank_value += score.fillna(0) * 0.55
    if confidence is not None:
        rank_value += confidence.fillna(0) * 0.30
    if opportunity is not None:
        rank_value += opportunity.fillna(0) * 0.15

    if float(rank_value.abs().sum()) > 0:
        df = df.assign(_dashboard_rank=rank_value).sort_values("_dashboard_rank", ascending=False)

    rows: list[dict[str, Any]] = []
    for _, row in df.head(limit).iterrows():
        rows.append(
            {
                "Symbol": str(_first_present(row, ["Symbol"], "—")).upper(),
                "Grade": _first_present(row, ["Grade"], "—"),
                "Setup": _first_present(row, ["Setup", "Setup Tag"], "—"),
                "Momo Score": _first_present(row, ["Momo Score", "Score"], None),
                "Momo Confidence": _first_present(row, ["Momo Confidence", "Confidence %", "Confidence"], None),
                "Price": _first_present(row, ["Price", "Close", "Current Price"], None),
                "RVOL": _first_present(row, ["RVOL", "Relative Volume"], None),
                "ATR %": _first_present(row, ["ATR %", "ATR%"], None),
            }
        )
    return rows


def recent_ai_recommendations(ai_reports: dict[Any, Any] | None, limit: int = 8) -> list[dict[str, Any]]:
    if not ai_reports:
        return []

    latest_by_symbol: dict[str, dict[str, Any]] = {}
    for key, report in ai_reports.items():
        if not isinstance(report, dict):
            continue
        symbol = str(report.get("symbol") or str(key).split("|", 1)[0]).upper().strip()
        if not symbol:
            continue
        item = {
            "Symbol": symbol,
            "Action": report.get("independent_action") or report.get("action") or report.get("recommendation") or "—",
            "AI Confidence": report.get("confidence"),
            "Sentiment": report.get("sentiment") or report.get("ai_sentiment") or "—",
            "Rating": report.get("final_rating") or report.get("rating") or "—",
            "Summary": report.get("executive_summary") or "",
            "Updated": report.get("generated_at") or report.get("timestamp") or "",
        }
        previous = latest_by_symbol.get(symbol)
        if previous is None or str(item["Updated"]) >= str(previous.get("Updated", "")):
            latest_by_symbol[symbol] = item

    values = list(latest_by_symbol.values())
    values.sort(key=lambda item: str(item.get("Updated", "")), reverse=True)
    return values[:limit]


def unread_watchlist_alerts(limit: int = 10) -> list[dict[str, Any]]:
    data = load_alerts()
    events = data.get("events", []) if isinstance(data, dict) else []
    unread = [event for event in events if not event.get("read")]
    unread.sort(key=lambda event: str(event.get("triggered_at") or event.get("created_at") or ""), reverse=True)
    return unread[:limit]


def load_open_trades(limit: int = 10) -> list[dict[str, Any]]:
    """Load persistent v0.85 Journal positions for the Morning Command Center."""
    if not TRADE_DATA_FILE.exists():
        return []
    try:
        payload = json.loads(TRADE_DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    raw = payload if isinstance(payload, list) else payload.get("trades", payload.get("items", [])) if isinstance(payload, dict) else []
    if isinstance(raw, dict):
        candidates = [item for item in raw.values() if isinstance(item, dict)]
    else:
        candidates = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []

    from datetime import datetime, timezone
    rows = []
    for trade in candidates:
        status = str(trade.get("status", "open")).lower()
        if status not in {"open", "active", "partial"}:
            continue
        shares = float(trade.get("shares") or 0)
        exits = trade.get("exits", []) if isinstance(trade.get("exits", []), list) else []
        exited = sum(float(item.get("shares") or 0) for item in exits if isinstance(item, dict))
        remaining = max(shares - exited, 0)
        updates = trade.get("updates", []) if isinstance(trade.get("updates", []), list) else []
        current = trade.get("current_price", trade.get("last_price"))
        if current is None:
            for update in updates:
                if isinstance(update, dict) and update.get("current_price") not in (None, ""):
                    current = update.get("current_price")
                    break
        unrealized = None
        try:
            if current is not None and remaining > 0:
                multiplier = 1 if str(trade.get("direction", "long")).lower() == "long" else -1
                unrealized = round((float(current) - float(trade.get("entry_price") or 0)) * remaining * multiplier, 2)
        except (TypeError, ValueError):
            pass
        held = None
        try:
            start_date = datetime.fromisoformat(str(trade.get("entry_date")).replace("Z", "+00:00"))
            held = max((datetime.now(timezone.utc).date() - start_date.date()).days, 0)
        except (TypeError, ValueError):
            pass
        rows.append({
            "Symbol": str(trade.get("symbol", "—")).upper(),
            "Entry": trade.get("entry_price", trade.get("entry")),
            "Current": current,
            "P/L": unrealized,
            "Remaining": remaining,
            "Stop": trade.get("current_stop", trade.get("stop")),
            "Target": trade.get("t1", trade.get("target")),
            "Days Held": held,
            "AI Confidence": trade.get("ai_confidence"),
            "Momo Score": trade.get("momo_score"),
        })
    return rows[:limit]


def market_index_rows(market_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not market_context:
        return []
    indexes = market_context.get("indexes", {})
    rows = []
    for symbol in ("SPY", "QQQ", "IWM", "DIA", "VIXY"):
        item = indexes.get(symbol, {})
        rows.append(
            {
                "Symbol": symbol,
                "Trend": item.get("trend", "—"),
                "Score": item.get("score"),
                "Price": item.get("close"),
                "5D %": item.get("return_5d_pct"),
                "20D %": item.get("return_20d_pct"),
                "Above EMA21": item.get("above_ema21"),
                "EMA Stack": item.get("ema_stack_bullish"),
                "RSI": item.get("rsi14"),
            }
        )
    return rows


def sector_rows(market_context: dict[str, Any] | None, limit: int = 6) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sectors = (market_context or {}).get("sectors", {})
    return list(sectors.get("leaders", []))[:limit], list(sectors.get("laggards", []))[:limit]

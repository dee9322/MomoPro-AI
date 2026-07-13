from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd

from trade_journal import average_exit_price, days_held, realized_pnl, realized_r
from trade_models import TradeRecord


SOURCE_OPTIONS = [
    "All Trades",
    "Webull / Broker Imported",
    "MomoPro Planned",
    "Manual Only",
]


def _parse_datetime(value: Any) -> pd.Timestamp | None:
    if value in (None, ""):
        return None
    try:
        parsed = pd.to_datetime(value, utc=True, errors="coerce")
        return None if pd.isna(parsed) else parsed
    except Exception:
        return None


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
        return number if pd.notna(number) else None
    except (TypeError, ValueError):
        return None


def trade_source_label(trade: TradeRecord) -> str:
    source = str(trade.source or "manual").lower()
    if source == "broker_import":
        return "Webull Imported"
    if source == "journal+broker":
        return "MomoPro + Webull"
    return "MomoPro Manual"


def is_momopro_planned(trade: TradeRecord) -> bool:
    return str(trade.source or "manual").lower() in {"manual", "journal+broker"}


def _trade_net_pnl(trade: TradeRecord) -> float:
    return round(realized_pnl(trade) - float(trade.broker_fees or 0), 2)


def _outcome(net_pnl: float) -> str:
    if net_pnl > 0.005:
        return "Win"
    if net_pnl < -0.005:
        return "Loss"
    return "Breakeven"


def _price_bucket(entry: float) -> str:
    if entry < 3:
        return "Under $3"
    if entry < 5:
        return "$3–$5"
    if entry < 10:
        return "$5–$10"
    if entry < 20:
        return "$10–$20"
    if entry < 50:
        return "$20–$50"
    return "$50+"


def _score_bucket(value: float | None) -> str:
    if value is None:
        return "Unknown"
    if value < 60:
        return "Below 60"
    if value < 70:
        return "60–69"
    if value < 80:
        return "70–79"
    if value < 90:
        return "80–89"
    return "90–100"


def _hold_bucket(days: int | None) -> str:
    if days is None:
        return "Unknown"
    if days <= 1:
        return "0–1 days"
    if days <= 3:
        return "2–3 days"
    if days <= 7:
        return "4–7 days"
    if days <= 14:
        return "8–14 days"
    if days <= 30:
        return "15–30 days"
    return "31+ days"


def _target_hit(trade: TradeRecord) -> bool | None:
    if trade.t1 is None or not trade.exits:
        return None
    if trade.direction.lower() == "short":
        return any(float(exit.price) <= float(trade.t1) for exit in trade.exits)
    return any(float(exit.price) >= float(trade.t1) for exit in trade.exits)


def _stop_hit(trade: TradeRecord) -> bool | None:
    stop = trade.initial_stop if trade.initial_stop is not None else trade.current_stop
    if stop is None or not trade.exits:
        return None
    if trade.direction.lower() == "short":
        return any(float(exit.price) >= float(stop) for exit in trade.exits)
    return any(float(exit.price) <= float(stop) for exit in trade.exits)


def trades_to_frame(trades: Iterable[TradeRecord]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for trade in trades:
        if not trade.exits:
            continue
        gross_pnl = realized_pnl(trade)
        net_pnl = _trade_net_pnl(trade)
        exit_time = _parse_datetime(trade.exit_date or max((item.date for item in trade.exits), default=None))
        entry_time = _parse_datetime(trade.entry_date)
        hold_days = days_held(trade)
        avg_exit = average_exit_price(trade)
        rows.append(
            {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "status": trade.status.title(),
                "source": trade_source_label(trade),
                "is_momopro_planned": is_momopro_planned(trade),
                "broker": trade.broker or "—",
                "entry_date": entry_time,
                "exit_date": exit_time,
                "entry_price": float(trade.entry_price or 0),
                "average_exit_price": avg_exit,
                "shares": float(trade.shares or 0),
                "gross_pnl": gross_pnl,
                "fees": float(trade.broker_fees or 0),
                "net_pnl": net_pnl,
                "outcome": _outcome(net_pnl),
                "realized_r": realized_r(trade),
                "days_held": hold_days,
                "hold_bucket": _hold_bucket(hold_days),
                "setup": trade.setup or "Unknown",
                "grade": trade.grade or "Unknown",
                "momo_score": _number(trade.momo_score),
                "momo_score_band": _score_bucket(_number(trade.momo_score)),
                "momo_confidence": _number(trade.momo_confidence),
                "opportunity_score": _number(trade.opportunity_score),
                "opportunity_band": _score_bucket(_number(trade.opportunity_score)),
                "ai_confidence": _number(trade.ai_confidence),
                "ai_confidence_band": _score_bucket(_number(trade.ai_confidence)),
                "ai_action": trade.ai_action or "Unknown",
                "market_regime": trade.market_regime or "Unknown",
                "sector": trade.sector_context or "Unknown",
                "price_range": _price_bucket(float(trade.entry_price or 0)),
                "planned_exit_followed": trade.planned_exit_followed or "Not Reviewed",
                "rule_following_score": _number(trade.rule_following_score),
                "mistakes": trade.mistakes.strip() if trade.mistakes else "",
                "strengths": trade.strengths.strip() if trade.strengths else "",
                "lessons": trade.lessons.strip() if trade.lessons else "",
                "target_hit": _target_hit(trade),
                "stop_hit": _stop_hit(trade),
                "exit_reason": trade.exit_reason or (trade.exits[-1].reason if trade.exits else ""),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["exit_date", "entry_date"], na_position="last").reset_index(drop=True)
    return frame


def filter_performance_frame(
    frame: pd.DataFrame,
    source: str = "All Trades",
    symbols: list[str] | None = None,
    start_date: Any = None,
    end_date: Any = None,
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    if source == "Webull / Broker Imported":
        result = result[result["source"].isin(["Webull Imported", "MomoPro + Webull"])]
    elif source == "MomoPro Planned":
        result = result[result["is_momopro_planned"]]
    elif source == "Manual Only":
        result = result[result["source"] == "MomoPro Manual"]
    if symbols:
        result = result[result["symbol"].isin(symbols)]
    if start_date is not None:
        start = pd.Timestamp(start_date, tz="UTC")
        result = result[result["exit_date"].isna() | (result["exit_date"] >= start)]
    if end_date is not None:
        end = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1)
        result = result[result["exit_date"].isna() | (result["exit_date"] < end)]
    return result.reset_index(drop=True)


def _streaks(outcomes: list[str]) -> dict[str, int]:
    longest_win = longest_loss = current_win = current_loss = 0
    run_type = None
    run_length = 0
    for outcome in outcomes:
        normalized = "Win" if outcome == "Win" else "Loss" if outcome == "Loss" else "Breakeven"
        if normalized == run_type:
            run_length += 1
        else:
            run_type, run_length = normalized, 1
        if normalized == "Win":
            longest_win = max(longest_win, run_length)
        elif normalized == "Loss":
            longest_loss = max(longest_loss, run_length)
    for outcome in reversed(outcomes):
        if outcome == "Win":
            current_win += 1
        else:
            break
    for outcome in reversed(outcomes):
        if outcome == "Loss":
            current_loss += 1
        else:
            break
    return {
        "longest_win_streak": longest_win,
        "longest_loss_streak": longest_loss,
        "current_win_streak": current_win,
        "current_loss_streak": current_loss,
    }


def calculate_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "trades": 0, "wins": 0, "losses": 0, "breakeven": 0, "win_rate": None,
            "gross_pnl": 0.0, "fees": 0.0, "net_pnl": 0.0, "avg_winner": None,
            "avg_loser": None, "profit_factor": None, "expectancy": None, "average_r": None,
            "average_hold_days": None, "best_trade": None, "worst_trade": None,
            "longest_win_streak": 0, "longest_loss_streak": 0,
            "current_win_streak": 0, "current_loss_streak": 0,
        }
    wins = frame[frame["net_pnl"] > 0]
    losses = frame[frame["net_pnl"] < 0]
    total = len(frame)
    gross_profit = float(wins["net_pnl"].sum())
    gross_loss = abs(float(losses["net_pnl"].sum()))
    r_values = pd.to_numeric(frame["realized_r"], errors="coerce").dropna()
    hold_values = pd.to_numeric(frame["days_held"], errors="coerce").dropna()
    best_idx = frame["net_pnl"].idxmax()
    worst_idx = frame["net_pnl"].idxmin()
    streak_data = _streaks(frame["outcome"].tolist())
    return {
        "trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": total - len(wins) - len(losses),
        "win_rate": round(len(wins) / total * 100, 2) if total else None,
        "gross_pnl": round(float(frame["gross_pnl"].sum()), 2),
        "fees": round(float(frame["fees"].sum()), 2),
        "net_pnl": round(float(frame["net_pnl"].sum()), 2),
        "avg_winner": round(float(wins["net_pnl"].mean()), 2) if not wins.empty else None,
        "avg_loser": round(float(losses["net_pnl"].mean()), 2) if not losses.empty else None,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
        "expectancy": round(float(frame["net_pnl"].mean()), 2),
        "average_r": round(float(r_values.mean()), 2) if not r_values.empty else None,
        "average_hold_days": round(float(hold_values.mean()), 1) if not hold_values.empty else None,
        "best_trade": frame.loc[best_idx].to_dict(),
        "worst_trade": frame.loc[worst_idx].to_dict(),
        **streak_data,
    }


def equity_curve(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Date", "Cumulative P/L"])
    curve = frame.dropna(subset=["exit_date"]).copy()
    if curve.empty:
        return pd.DataFrame(columns=["Date", "Cumulative P/L"])
    curve = curve.sort_values("exit_date")
    curve["Cumulative P/L"] = curve["net_pnl"].cumsum()
    curve["Date"] = curve["exit_date"].dt.date
    return curve[["Date", "Cumulative P/L", "symbol", "net_pnl"]]


def monthly_performance(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    data = frame.dropna(subset=["exit_date"]).copy()
    if data.empty:
        return pd.DataFrame()
    data["Month"] = data["exit_date"].dt.tz_convert(None).dt.to_period("M").astype(str)
    grouped = data.groupby("Month", dropna=False)
    result = grouped.agg(
        Trades=("trade_id", "count"),
        Net_PnL=("net_pnl", "sum"),
        Wins=("outcome", lambda values: int((values == "Win").sum())),
        Avg_R=("realized_r", "mean"),
    ).reset_index()
    result["Win Rate %"] = (result["Wins"] / result["Trades"] * 100).round(2)
    result["Net P/L"] = result.pop("Net_PnL").round(2)
    result["Average R"] = result.pop("Avg_R").round(2)
    return result[["Month", "Trades", "Win Rate %", "Net P/L", "Average R"]]


def group_performance(frame: pd.DataFrame, column: str, label: str | None = None) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return pd.DataFrame()
    data = frame.copy()
    data[column] = data[column].fillna("Unknown").replace("", "Unknown")
    grouped = data.groupby(column, dropna=False)
    result = grouped.agg(
        Trades=("trade_id", "count"),
        Wins=("outcome", lambda values: int((values == "Win").sum())),
        Net_PnL=("net_pnl", "sum"),
        Average_PnL=("net_pnl", "mean"),
        Average_R=("realized_r", "mean"),
    ).reset_index()
    result["Win Rate %"] = (result["Wins"] / result["Trades"] * 100).round(2)
    result = result.rename(columns={
        column: label or column.replace("_", " ").title(),
        "Net_PnL": "Net P/L",
        "Average_PnL": "Average P/L",
        "Average_R": "Average R",
    })
    result["Net P/L"] = result["Net P/L"].round(2)
    result["Average P/L"] = result["Average P/L"].round(2)
    result["Average R"] = result["Average R"].round(2)
    return result.sort_values(["Net P/L", "Trades"], ascending=[False, False]).reset_index(drop=True)


def review_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {}
    reviewed = frame[frame["planned_exit_followed"] != "Not Reviewed"]
    rule_scores = pd.to_numeric(frame["rule_following_score"], errors="coerce").dropna()
    target_known = frame[frame["target_hit"].notna()]
    stop_known = frame[frame["stop_hit"].notna()]
    with_mistakes = frame[frame["mistakes"].astype(str).str.strip() != ""]
    return {
        "reviewed_trades": len(reviewed),
        "planned_exit_follow_rate": round((reviewed["planned_exit_followed"].astype(str).str.lower() == "yes").mean() * 100, 2) if len(reviewed) else None,
        "average_rule_score": round(float(rule_scores.mean()), 1) if not rule_scores.empty else None,
        "mistake_rate": round(len(with_mistakes) / len(frame) * 100, 2) if len(frame) else None,
        "target_hit_rate": round(target_known["target_hit"].astype(bool).mean() * 100, 2) if len(target_known) else None,
        "stop_hit_rate": round(stop_known["stop_hit"].astype(bool).mean() * 100, 2) if len(stop_known) else None,
    }


def decision_accuracy(frame: pd.DataFrame, field: str, bullish_terms: set[str]) -> dict[str, Any]:
    if frame.empty or field not in frame.columns:
        return {"coverage": 0, "accuracy": None, "sample": 0}
    data = frame[frame[field].notna() & (frame[field].astype(str).str.strip() != "") & (frame[field] != "Unknown")].copy()
    if data.empty:
        return {"coverage": 0, "accuracy": None, "sample": 0}
    normalized = data[field].astype(str).str.lower()
    predictions = normalized.apply(lambda value: any(term in value for term in bullish_terms))
    actual = data["net_pnl"] > 0
    accuracy = (predictions == actual).mean() * 100
    return {
        "coverage": round(len(data) / len(frame) * 100, 2),
        "accuracy": round(float(accuracy), 2),
        "sample": len(data),
    }


def data_quality_report(frame: pd.DataFrame, executions: list[Any], imports: list[Any]) -> dict[str, Any]:
    total_exec = len(executions)
    matched = sum(1 for item in executions if getattr(item, "matched_trade_id", ""))
    unmatched = total_exec - matched
    return {
        "closed_trade_records": len(frame),
        "broker_executions": total_exec,
        "matched_executions": matched,
        "unmatched_executions": unmatched,
        "reconciliation_rate": round(matched / total_exec * 100, 2) if total_exec else None,
        "imports": len(imports),
        "trades_with_r": int(frame["realized_r"].notna().sum()) if not frame.empty else 0,
        "trades_with_ai": int(frame["ai_confidence"].notna().sum()) if not frame.empty else 0,
        "trades_with_setup": int((frame["setup"] != "Unknown").sum()) if not frame.empty else 0,
        "trades_reviewed": int((frame["planned_exit_followed"] != "Not Reviewed").sum()) if not frame.empty else 0,
    }


def trade_timeline(trade: TradeRecord) -> pd.DataFrame:
    events: list[dict[str, Any]] = [{
        "Date": trade.entry_date,
        "Event": "Entry",
        "Details": f"{trade.shares:g} shares @ ${trade.entry_price:.4f}",
    }]
    for update in trade.updates:
        details = update.note or update.update_type
        if update.stop is not None:
            details += f" · Stop ${float(update.stop):.4f}"
        if update.current_price is not None:
            details += f" · Price ${float(update.current_price):.4f}"
        events.append({"Date": update.date, "Event": update.update_type, "Details": details})
    for exit_item in trade.exits:
        events.append({
            "Date": exit_item.date,
            "Event": "Exit",
            "Details": f"{exit_item.shares:g} shares @ ${exit_item.price:.4f} · {exit_item.reason or 'Exit'}",
        })
    result = pd.DataFrame(events)
    if not result.empty:
        result["_sort"] = pd.to_datetime(result["Date"], utc=True, errors="coerce")
        result = result.sort_values("_sort", na_position="last").drop(columns=["_sort"])
    return result.reset_index(drop=True)

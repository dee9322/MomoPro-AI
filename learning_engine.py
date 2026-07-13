from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd


EVIDENCE_LEVELS = (
    (50, "Strong evidence"),
    (20, "Moderate evidence"),
    (8, "Early signal"),
    (0, "Insufficient data"),
)


def evidence_level(sample_size: int) -> str:
    size = max(int(sample_size or 0), 0)
    for threshold, label in EVIDENCE_LEVELS:
        if size >= threshold:
            return label
    return "Insufficient data"


def confidence_weight(sample_size: int) -> float:
    """Conservative 0-1 confidence weight; deliberately slow to reach 1.0."""
    size = max(int(sample_size or 0), 0)
    return round(min(size / 50.0, 1.0), 4)


def _safe_mean(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return None if values.empty else float(values.mean())


def _safe_sum(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").fillna(0)
    return float(values.sum())


def _win_rate(frame: pd.DataFrame) -> float | None:
    if frame.empty:
        return None
    decided = frame[frame["outcome"].isin(["Win", "Loss"])]
    if decided.empty:
        return None
    return float((decided["outcome"] == "Win").mean() * 100)


def _group_stats(frame: pd.DataFrame, column: str, minimum_samples: int = 2) -> pd.DataFrame:
    columns = [
        "Group", "Trades", "Wins", "Losses", "Win Rate %", "Net P/L",
        "Expectancy", "Average R", "Average Hold Days", "Evidence",
    ]
    if frame.empty or column not in frame.columns:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    for group, subset in frame.groupby(column, dropna=False):
        label = str(group).strip() if pd.notna(group) and str(group).strip() else "Unknown"
        trades = len(subset)
        if trades < minimum_samples:
            continue
        rows.append({
            "Group": label,
            "Trades": trades,
            "Wins": int((subset["outcome"] == "Win").sum()),
            "Losses": int((subset["outcome"] == "Loss").sum()),
            "Win Rate %": round(_win_rate(subset), 2) if _win_rate(subset) is not None else None,
            "Net P/L": round(_safe_sum(subset["net_pnl"]), 2),
            "Expectancy": round(_safe_mean(subset["net_pnl"]), 2) if _safe_mean(subset["net_pnl"]) is not None else None,
            "Average R": round(_safe_mean(subset["realized_r"]), 2) if _safe_mean(subset["realized_r"]) is not None else None,
            "Average Hold Days": round(_safe_mean(subset["days_held"]), 2) if _safe_mean(subset["days_held"]) is not None else None,
            "Evidence": evidence_level(trades),
        })
    result = pd.DataFrame(rows, columns=columns)
    if result.empty:
        return result
    return result.sort_values(["Expectancy", "Trades"], ascending=[False, False], na_position="last").reset_index(drop=True)


def edge_tables(frame: pd.DataFrame, minimum_samples: int = 2) -> dict[str, pd.DataFrame]:
    dimensions = {
        "Setups": "setup",
        "Grades": "grade",
        "Market Regimes": "market_regime",
        "Sectors": "sector",
        "Price Ranges": "price_range",
        "Hold Durations": "hold_bucket",
        "Momo Score": "momo_score_band",
        "Opportunity Score": "opportunity_band",
        "AI Confidence": "ai_confidence_band",
        "Trade Source": "source",
    }
    return {name: _group_stats(frame, column, minimum_samples) for name, column in dimensions.items()}


def strongest_edges(tables: dict[str, pd.DataFrame], limit: int = 8) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for dimension, table in tables.items():
        if table.empty:
            continue
        for _, row in table.iterrows():
            if row.get("Expectancy") is None or pd.isna(row.get("Expectancy")):
                continue
            rows.append({"Dimension": dimension, **row.to_dict()})
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["Reliability Weight"] = result["Trades"].apply(confidence_weight)
    result["Adjusted Edge"] = result["Expectancy"] * result["Reliability Weight"]
    return result.sort_values(["Adjusted Edge", "Trades"], ascending=[False, False]).head(limit).reset_index(drop=True)


def weakest_areas(tables: dict[str, pd.DataFrame], limit: int = 8) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for dimension, table in tables.items():
        if table.empty:
            continue
        for _, row in table.iterrows():
            expectancy = row.get("Expectancy")
            if expectancy is None or pd.isna(expectancy):
                continue
            rows.append({"Dimension": dimension, **row.to_dict()})
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["Reliability Weight"] = result["Trades"].apply(confidence_weight)
    result["Adjusted Weakness"] = result["Expectancy"] * result["Reliability Weight"]
    return result.sort_values(["Adjusted Weakness", "Trades"], ascending=[True, False]).head(limit).reset_index(drop=True)


def calibration_table(frame: pd.DataFrame, band_column: str, label: str) -> pd.DataFrame:
    columns = [label, "Trades", "Win Rate %", "Average P/L", "Average R", "Evidence"]
    if frame.empty or band_column not in frame.columns:
        return pd.DataFrame(columns=columns)
    rows = []
    for band, subset in frame.groupby(band_column, dropna=False):
        band_text = str(band or "Unknown")
        if band_text == "Unknown":
            continue
        rows.append({
            label: band_text,
            "Trades": len(subset),
            "Win Rate %": round(_win_rate(subset), 2) if _win_rate(subset) is not None else None,
            "Average P/L": round(_safe_mean(subset["net_pnl"]), 2) if _safe_mean(subset["net_pnl"]) is not None else None,
            "Average R": round(_safe_mean(subset["realized_r"]), 2) if _safe_mean(subset["realized_r"]) is not None else None,
            "Evidence": evidence_level(len(subset)),
        })
    return pd.DataFrame(rows, columns=columns)


def mistake_learning(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["Mistake", "Occurrences", "Net P/L", "Average P/L", "Win Rate %", "Evidence"]
    if frame.empty or "mistakes" not in frame.columns:
        return pd.DataFrame(columns=columns)
    exploded: list[dict[str, Any]] = []
    separators = [";", "\n", "|"]
    for _, row in frame.iterrows():
        text = str(row.get("mistakes") or "").strip()
        if not text:
            continue
        normalized = text
        for separator in separators:
            normalized = normalized.replace(separator, ",")
        labels = [item.strip() for item in normalized.split(",") if item.strip()]
        for label in labels:
            exploded.append({"mistake": label, "net_pnl": row.get("net_pnl"), "outcome": row.get("outcome")})
    if not exploded:
        return pd.DataFrame(columns=columns)
    data = pd.DataFrame(exploded)
    rows = []
    for mistake, subset in data.groupby("mistake"):
        rows.append({
            "Mistake": mistake,
            "Occurrences": len(subset),
            "Net P/L": round(_safe_sum(subset["net_pnl"]), 2),
            "Average P/L": round(_safe_mean(subset["net_pnl"]), 2) if _safe_mean(subset["net_pnl"]) is not None else None,
            "Win Rate %": round(_win_rate(subset), 2) if _win_rate(subset) is not None else None,
            "Evidence": evidence_level(len(subset)),
        })
    return pd.DataFrame(rows, columns=columns).sort_values(["Occurrences", "Net P/L"], ascending=[False, True]).reset_index(drop=True)


def behavior_signals(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"sample_size": 0, "evidence": "Insufficient data", "signals": []}
    signals: list[dict[str, Any]] = []

    winners = frame[frame["outcome"] == "Win"]
    losers = frame[frame["outcome"] == "Loss"]
    avg_win_hold = _safe_mean(winners["days_held"]) if not winners.empty else None
    avg_loss_hold = _safe_mean(losers["days_held"]) if not losers.empty else None
    if avg_win_hold is not None and avg_loss_hold is not None and avg_loss_hold > avg_win_hold * 1.35:
        signals.append({"type": "Risk", "name": "Holding losers longer", "detail": f"Losses average {avg_loss_hold:.1f} days versus {avg_win_hold:.1f} days for winners."})

    reviewed = frame[pd.to_numeric(frame["rule_following_score"], errors="coerce").notna()]
    if len(reviewed) >= 3:
        score = _safe_mean(reviewed["rule_following_score"])
        if score is not None and score < 70:
            signals.append({"type": "Risk", "name": "Plan adherence", "detail": f"Average rule-following score is {score:.1f}/100."})
        elif score is not None and score >= 85:
            signals.append({"type": "Strength", "name": "Plan adherence", "detail": f"Average rule-following score is {score:.1f}/100."})

    followed = frame[frame["planned_exit_followed"].astype(str).str.lower().isin(["yes", "followed", "true"])]
    not_followed = frame[frame["planned_exit_followed"].astype(str).str.lower().isin(["no", "not followed", "false"])]
    if len(followed) >= 2 and len(not_followed) >= 2:
        followed_exp = _safe_mean(followed["net_pnl"])
        missed_exp = _safe_mean(not_followed["net_pnl"])
        if followed_exp is not None and missed_exp is not None:
            signals.append({
                "type": "Learning",
                "name": "Plan-following impact",
                "detail": f"Following planned exits averages ${followed_exp:.2f} per trade versus ${missed_exp:.2f} when not followed.",
            })

    return {"sample_size": len(frame), "evidence": evidence_level(len(frame)), "signals": signals}


def weekly_monthly_review(frame: pd.DataFrame, period: str = "Weekly") -> dict[str, Any]:
    if frame.empty or "exit_date" not in frame.columns:
        return {"period": period, "trades": 0, "net_pnl": 0.0, "win_rate": None, "average_r": None, "evidence": "Insufficient data"}
    dated = frame.dropna(subset=["exit_date"]).copy()
    if dated.empty:
        return {"period": period, "trades": 0, "net_pnl": 0.0, "win_rate": None, "average_r": None, "evidence": "Insufficient data"}
    latest = dated["exit_date"].max()
    days = 7 if period.lower().startswith("week") else 30
    subset = dated[dated["exit_date"] >= latest - pd.Timedelta(days=days)]
    return {
        "period": period,
        "trades": len(subset),
        "net_pnl": round(_safe_sum(subset["net_pnl"]), 2),
        "win_rate": round(_win_rate(subset), 2) if _win_rate(subset) is not None else None,
        "average_r": round(_safe_mean(subset["realized_r"]), 2) if _safe_mean(subset["realized_r"]) is not None else None,
        "evidence": evidence_level(len(subset)),
    }


def build_learning_report(frame: pd.DataFrame, minimum_samples: int = 2) -> dict[str, Any]:
    tables = edge_tables(frame, minimum_samples)
    return {
        "sample_size": len(frame),
        "evidence": evidence_level(len(frame)),
        "tables": tables,
        "edges": strongest_edges(tables),
        "weaknesses": weakest_areas(tables),
        "ai_calibration": calibration_table(frame, "ai_confidence_band", "AI Confidence"),
        "momo_calibration": calibration_table(frame, "momo_score_band", "Momo Score"),
        "opportunity_calibration": calibration_table(frame, "opportunity_band", "Opportunity Score"),
        "mistakes": mistake_learning(frame),
        "behavior": behavior_signals(frame),
        "weekly": weekly_monthly_review(frame, "Weekly"),
        "monthly": weekly_monthly_review(frame, "Monthly"),
    }

from __future__ import annotations

from typing import Any

import pandas as pd

from performance_engine import group_performance


def _best_group(frame: pd.DataFrame, column: str, label: str) -> str | None:
    table = group_performance(frame, column, label)
    if table.empty:
        return None
    eligible = table[table["Trades"] >= 2]
    row = (eligible if not eligible.empty else table).iloc[0]
    return f"{row[label]} ({int(row['Trades'])} trades, ${float(row['Net P/L']):,.2f} net, {float(row['Win Rate %']):.1f}% wins)"


def _worst_group(frame: pd.DataFrame, column: str, label: str) -> str | None:
    table = group_performance(frame, column, label)
    if table.empty:
        return None
    eligible = table[table["Trades"] >= 2]
    row = (eligible if not eligible.empty else table).sort_values("Net P/L", ascending=True).iloc[0]
    return f"{row[label]} ({int(row['Trades'])} trades, ${float(row['Net P/L']):,.2f} net)"


def build_performance_insights(frame: pd.DataFrame, summary: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    if frame.empty:
        return {
            "headline": "Import or close trades to unlock performance intelligence.",
            "strengths": [],
            "risks": [],
            "next_actions": ["Import Webull history or complete a journal trade."],
        }

    strengths: list[str] = []
    risks: list[str] = []
    actions: list[str] = []

    win_rate = summary.get("win_rate")
    profit_factor = summary.get("profit_factor")
    expectancy = summary.get("expectancy")
    avg_r = summary.get("average_r")

    if profit_factor is not None and profit_factor >= 1.5:
        strengths.append(f"Profit factor is strong at {profit_factor:.2f}.")
    elif profit_factor is not None and profit_factor < 1.0:
        risks.append(f"Profit factor is below 1.0 at {profit_factor:.2f}; losses currently outweigh gains.")
        actions.append("Reduce loss size and review stop discipline before increasing risk.")

    if expectancy is not None and expectancy > 0:
        strengths.append(f"Average expectancy is positive at ${expectancy:,.2f} per completed trade.")
    elif expectancy is not None:
        risks.append(f"Average expectancy is ${expectancy:,.2f} per trade.")

    if avg_r is not None and avg_r >= 1:
        strengths.append(f"Average realized result is {avg_r:.2f}R.")
    elif avg_r is not None and avg_r < 0:
        risks.append(f"Average realized R is negative at {avg_r:.2f}R.")

    best_setup = _best_group(frame, "setup", "Setup")
    worst_setup = _worst_group(frame, "setup", "Setup")
    if best_setup and "Unknown" not in best_setup:
        strengths.append(f"Best-performing setup: {best_setup}.")
    if worst_setup and best_setup != worst_setup and "Unknown" not in worst_setup:
        risks.append(f"Weakest setup: {worst_setup}.")

    best_regime = _best_group(frame, "market_regime", "Market Regime")
    if best_regime and "Unknown" not in best_regime:
        strengths.append(f"Best market environment: {best_regime}.")

    rule_score = review.get("average_rule_score")
    if rule_score is not None and rule_score < 70:
        risks.append(f"Average rule-following score is {rule_score:.1f}/100.")
        actions.append("Review the lowest rule-following trades and identify one repeatable correction.")

    mistake_rate = review.get("mistake_rate")
    if mistake_rate is not None and mistake_rate >= 40:
        risks.append(f"Documented mistakes appear in {mistake_rate:.1f}% of completed trades.")
        actions.append("Group recurring mistakes and add a pre-trade checklist rule for the most common one.")

    planned_rate = review.get("planned_exit_follow_rate")
    if planned_rate is not None and planned_rate < 70:
        risks.append(f"Planned exits were followed in only {planned_rate:.1f}% of reviewed trades.")
        actions.append("Compare planned and actual exits before the next trading session.")

    coverage = {
        "setup": int((frame["setup"] != "Unknown").sum()),
        "ai": int(frame["ai_confidence"].notna().sum()),
        "r": int(frame["realized_r"].notna().sum()),
        "reviews": int((frame["planned_exit_followed"] != "Not Reviewed").sum()),
    }
    if coverage["setup"] < max(3, len(frame) * 0.25):
        actions.append("Add setup labels to more historical trades so strategy analytics become reliable.")
    if coverage["r"] < max(3, len(frame) * 0.25):
        actions.append("Add initial stops to more trades so R-multiple analytics become meaningful.")
    if coverage["ai"] < max(3, len(frame) * 0.25):
        actions.append("Future trades should preserve Independent AI Confidence at entry for calibration.")

    if not actions:
        actions.append("Keep collecting trades; larger samples will make setup and confidence calibration more reliable.")

    if summary.get("net_pnl", 0) > 0 and (profit_factor is None or profit_factor >= 1):
        headline = "Your completed-trade sample is profitable; focus on protecting the behaviors creating that edge."
    else:
        headline = "The current sample needs refinement; use the breakdowns below to isolate the strongest conditions."

    return {
        "headline": headline,
        "strengths": strengths[:5],
        "risks": risks[:5],
        "next_actions": actions[:5],
        "coverage": coverage,
    }

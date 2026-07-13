from __future__ import annotations

from typing import Any

import pandas as pd


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def build_coaching(report: dict[str, Any]) -> dict[str, list[str] | str]:
    sample = int(report.get("sample_size") or 0)
    evidence = str(report.get("evidence") or "Insufficient data")
    strengths: list[str] = []
    risks: list[str] = []
    priorities: list[str] = []

    edges = report.get("edges")
    if isinstance(edges, pd.DataFrame) and not edges.empty:
        for _, row in edges.head(3).iterrows():
            strengths.append(
                f"{row['Dimension']}: {row['Group']} has averaged {_money(row['Expectancy'])} per trade "
                f"across {int(row['Trades'])} trades ({row['Evidence'].lower()})."
            )

    weak = report.get("weaknesses")
    if isinstance(weak, pd.DataFrame) and not weak.empty:
        for _, row in weak.head(3).iterrows():
            risks.append(
                f"{row['Dimension']}: {row['Group']} has averaged {_money(row['Expectancy'])} per trade "
                f"across {int(row['Trades'])} trades ({row['Evidence'].lower()})."
            )

    mistakes = report.get("mistakes")
    if isinstance(mistakes, pd.DataFrame) and not mistakes.empty:
        first = mistakes.iloc[0]
        risks.append(f"Most frequently documented mistake: {first['Mistake']} ({int(first['Occurrences'])} occurrences).")
        priorities.append(f"Create one concrete rule to reduce '{first['Mistake']}' on the next five trades.")

    behavior = report.get("behavior", {})
    for signal in behavior.get("signals", []):
        line = f"{signal.get('name')}: {signal.get('detail')}"
        if signal.get("type") == "Strength":
            strengths.append(line)
        else:
            risks.append(line)

    if not priorities:
        if risks:
            priorities.append("Focus the next review cycle on the first documented weak area and measure whether expectancy improves.")
        elif strengths:
            priorities.append("Protect the strongest observed edge while collecting a larger sample before changing strategy rules.")
        else:
            priorities.append("Complete post-trade reviews and record setup, stop, scores, and market context so personalized learning can begin.")

    if sample < 8:
        disclaimer = (
            f"Only {sample} completed trades are available. Treat all conclusions as descriptive, not predictive. "
            "MomoPro will strengthen or withdraw conclusions as the sample grows."
        )
    else:
        disclaimer = f"Evidence level: {evidence}. Conclusions are based only on recorded journal fields and broker executions."

    return {"strengths": strengths, "risks": risks, "priorities": priorities, "disclaimer": disclaimer}

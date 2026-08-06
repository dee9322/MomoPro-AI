"""Reusable UI components for consistent status, diagnostics and empty states."""
from __future__ import annotations

from typing import Iterable, Mapping, Any

import streamlit as st


def render_health_monitor(checks: Iterable[Any], timings: Mapping[str, float] | None = None) -> None:
    with st.expander("System Health", expanded=False):
        rows = []
        for check in checks:
            row = check.to_dict() if hasattr(check, "to_dict") else dict(check)
            icon = {"ok": "🟢", "warning": "🟡", "error": "🔴"}.get(row.get("status"), "⚪")
            rows.append({"Status": icon, "Service": row.get("name", "Unknown"), "Detail": row.get("detail", "")})
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        if timings:
            st.caption("Startup timings (milliseconds)")
            st.dataframe(
                [{"Step": k, "Milliseconds": v} for k, v in timings.items()],
                width="stretch", hide_index=True,
            )


def render_error_diagnostic(title: str, *, reason: str, retry_label: str | None = None, key: str | None = None) -> bool:
    st.warning(f"{title}\n\nReason: {reason}")
    if retry_label:
        return st.button(retry_label, key=key, width="stretch")
    return False

"""Startup checks and provider-health diagnostics."""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, asdict
from typing import Any, Iterable


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _module(name: str) -> Check:
    return Check(name, "ok" if importlib.util.find_spec(name) else "warning", "installed" if importlib.util.find_spec(name) else "not installed")


def run_startup_checks(*, supabase_configured: bool, secrets: Iterable[str] = ()) -> list[Check]:
    checks = [
        Check("Python project", "ok", "source loaded"),
        Check("Supabase", "ok" if supabase_configured else "warning", "configured" if supabase_configured else "local fallback mode"),
        _module("streamlit"),
        _module("pandas"),
        _module("alpaca"),
    ]
    secret_names = set(secrets)
    for name in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "OPENAI_API_KEY"):
        checks.append(Check(name, "ok" if name in secret_names else "warning", "available" if name in secret_names else "missing"))
    for path in (".",):
        checks.append(Check("Runtime directory", "ok" if os.access(path, os.R_OK | os.W_OK) else "error", os.path.abspath(path)))
    return checks


def overall_status(checks: list[Check]) -> str:
    statuses = {c.status for c in checks}
    return "error" if "error" in statuses else "warning" if "warning" in statuses else "ok"

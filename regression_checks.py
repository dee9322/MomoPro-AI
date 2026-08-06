"""Fast static regression checks for release candidates."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run() -> list[str]:
    errors: list[str] = []
    for path in ROOT.glob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    forbidden = {
        "selected_stock.to_dict()": "unsafe direct-symbol conversion",
        "use_container_width=True": "deprecated Streamlit width API",
    }
    for text, reason in forbidden.items():
        if text in app:
            errors.append(f"app.py contains {reason}: {text}")
    required = ["cache_policy.py", "diagnostics.py", "logging_config.py", "ui_components.py", "data_services.py"]
    for name in required:
        if not (ROOT / name).exists():
            errors.append(f"missing required maintainability module: {name}")
    return errors


if __name__ == "__main__":
    failures = run()
    if failures:
        raise SystemExit("\n".join(failures))
    print("v0.98.6 regression checks passed")

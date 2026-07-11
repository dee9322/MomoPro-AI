from __future__ import annotations
from typing import Any


def calculate_intelligent_targets(stock: Any, pattern: dict) -> dict:
    def val(key):
        try:
            x = stock.get(key)
            return float(x) if x is not None else None
        except Exception:
            return None
    entry = val("Reference Entry") or val("Close")
    risk = val("Risk Per Share")
    structural = [val("T1"), val("T2"), val("T3")]
    atr_pct = val("ATR %") or 4
    atr = entry * atr_pct / 100 if entry else None
    if entry is None:
        return {"targets": []}
    measured_multiplier = 2.0 if pattern.get("primary_pattern") in {"Bull Flag / Tight Consolidation", "Ascending Triangle"} else 1.5
    measured = entry + atr * measured_multiplier if atr else None
    outputs = []
    for idx in range(3):
        target = structural[idx]
        if target is None and atr is not None:
            target = entry + atr * (1.25 + idx * 0.75)
        r_multiple = ((target - entry) / risk) if target is not None and risk and risk > 0 else None
        outputs.append({
            "name": f"T{idx+1}",
            "price": round(target, 2) if target is not None else None,
            "upside_pct": round((target - entry) / entry * 100, 2) if target is not None else None,
            "r_multiple": round(r_multiple, 2) if r_multiple is not None else None,
            "source": "Structural resistance" if structural[idx] is not None else "ATR fallback",
        })
    return {"targets": outputs, "measured_move_reference": round(measured, 2) if measured else None}

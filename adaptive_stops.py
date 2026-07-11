from __future__ import annotations
from typing import Any


def calculate_adaptive_stops(stock: Any) -> dict:
    def val(key):
        try:
            x = stock.get(key)
            return float(x) if x is not None else None
        except Exception:
            return None
    entry = val("Reference Entry") or val("Close")
    supports = [val("Support 1"), val("Support 2"), val("Support 3")]
    supports = [x for x in supports if x is not None and entry is not None and x < entry]
    atr_pct = val("ATR %") or 4
    atr = entry * atr_pct / 100 if entry else None
    if entry is None:
        return {"aggressive": None, "standard": None, "conservative": None, "notes": []}
    nearest = supports[0] if len(supports) > 0 else entry - atr * 0.75
    second = supports[1] if len(supports) > 1 else entry - atr * 1.25
    third = supports[2] if len(supports) > 2 else entry - atr * 1.75
    aggressive = min(nearest - atr * 0.10, entry - atr * 0.45)
    standard = min(second - atr * 0.10, entry - atr * 0.90)
    conservative = min(third - atr * 0.10, entry - atr * 1.40)
    return {
        "aggressive": round(max(0.01, aggressive), 2),
        "standard": round(max(0.01, standard), 2),
        "conservative": round(max(0.01, conservative), 2),
        "notes": [
            "Aggressive stop prioritizes tight risk near the closest support.",
            "Standard stop allows normal swing volatility below deeper structure.",
            "Conservative stop prioritizes structural invalidation over position size.",
        ],
    }

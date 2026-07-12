from __future__ import annotations

from typing import Any, Dict, Tuple

RULE_TYPES = {
    "Price Above": "price_above", "Price Below": "price_below",
    "Opportunity At Least": "opportunity_min", "Confidence At Least": "confidence_min",
    "Momo Score At Least": "momo_min", "RVOL At Least": "rvol_min",
    "Grade Becomes": "grade_equals", "Setup Contains": "setup_contains",
    "Thesis Status Becomes": "thesis_equals", "AI Recommendation Becomes": "recommendation_equals",
}


def evaluate_rule(rule: Dict[str, Any], snapshot: Dict[str, Any]) -> Tuple[bool, str]:
    kind, target = rule.get("type"), rule.get("value")
    tech, ai = snapshot.get("technical", {}), snapshot.get("ai_state", {})
    def num(value):
        try: return float(value)
        except (TypeError, ValueError): return None
    mapping = {
        "price_above": tech.get("price"), "price_below": tech.get("price"),
        "opportunity_min": ai.get("opportunity_score"), "confidence_min": tech.get("confidence"),
        "momo_min": tech.get("momo_score"), "rvol_min": tech.get("rvol"),
    }
    if kind in mapping:
        current, threshold = num(mapping[kind]), num(target)
        if current is None or threshold is None: return False, "Required value is unavailable."
        met = current >= threshold if kind not in ("price_below",) else current <= threshold
        return met, f"Current {current:g}; threshold {threshold:g}."
    text_map = {"grade_equals": tech.get("grade"), "setup_contains": tech.get("setup"),
                "thesis_equals": ai.get("thesis_status"), "recommendation_equals": ai.get("recommendation")}
    current = str(text_map.get(kind, ""))
    wanted = str(target or "")
    met = wanted.lower() in current.lower() if kind == "setup_contains" else current.lower() == wanted.lower()
    return met, f"Current value: {current or 'unavailable'}."

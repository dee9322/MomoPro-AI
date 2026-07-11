from __future__ import annotations

from typing import Any


def get_options_activity(
    symbol: str,
    finnhub_api_key: str | None = None,
    fmp_api_key: str | None = None,
) -> dict[str, Any]:
    """Return a clean unavailable state when reliable free options flow is absent.

    MomoPro intentionally does not call Alpha Vantage's premium options endpoint.
    A future paid or entitlement-backed provider can be connected here without
    changing the Smart Money coordinator or Stock Report UI.
    """
    return {
        "status": "Unavailable",
        "score": None,
        "bias": None,
        "call_volume": None,
        "put_volume": None,
        "put_call_volume_ratio": None,
        "unusual_contract_count": None,
        "unusual_contracts": [],
        "summary": "Reliable options-flow data is not available on the connected free plans.",
        "display_message": "Options flow unavailable on current data plans.",
        "disclaimer": (
            "No options score is included in Smart Money confidence. "
            "This module will activate only when a reliable entitled options source is connected."
        ),
    }

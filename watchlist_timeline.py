from __future__ import annotations
from watchlist_models import WatchlistItem, utc_now

def add_timeline_event(item: WatchlistItem, event: str, details: str = "") -> None:
    item.timeline.append({"timestamp": utc_now(), "event": event, "details": details})

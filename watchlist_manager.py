from __future__ import annotations

import re
from typing import Iterable, List, Tuple

from watchlist_models import WatchlistItem, utc_now
from watchlist_storage import get_item, load_data, put_item, save_data

_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


def normalize_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    if not _SYMBOL.fullmatch(value):
        raise ValueError("Ticker must be 1-10 characters using letters, numbers, periods, or hyphens.")
    return value


def list_watchlists() -> List[str]:
    return list(load_data()["watchlists"].keys())


def create_watchlist(name: str) -> None:
    clean = str(name or "").strip()
    if not clean:
        raise ValueError("Watchlist name is required.")
    data = load_data()
    if clean in data["watchlists"]:
        raise ValueError("That watchlist already exists.")
    data["watchlists"][clean] = []
    save_data(data)


def rename_watchlist(old_name: str, new_name: str) -> None:
    clean = str(new_name or "").strip()
    data = load_data()
    if old_name not in data["watchlists"]:
        raise ValueError("Watchlist not found.")
    if not clean or clean in data["watchlists"]:
        raise ValueError("Choose a new, unique watchlist name.")
    rebuilt = {}
    for key, value in data["watchlists"].items():
        rebuilt[clean if key == old_name else key] = value
    data["watchlists"] = rebuilt
    save_data(data)


def delete_watchlist(name: str) -> None:
    data = load_data()
    if name not in data["watchlists"]:
        return
    if len(data["watchlists"]) == 1:
        raise ValueError("At least one watchlist must remain.")
    del data["watchlists"][name]
    save_data(data)


def add_symbols(watchlist: str, symbols: Iterable[str]) -> Tuple[List[str], List[str]]:
    data = load_data()
    if watchlist not in data["watchlists"]:
        raise ValueError("Watchlist not found.")
    added, skipped = [], []
    current = data["watchlists"][watchlist]
    for raw in symbols:
        try:
            symbol = normalize_symbol(raw)
        except ValueError:
            skipped.append(str(raw))
            continue
        if symbol in current:
            skipped.append(symbol)
            continue
        current.append(symbol)
        item = get_item(data, symbol) or WatchlistItem(symbol=symbol)
        item.timeline.append({"timestamp": utc_now(), "event": "Saved", "details": f"Added to {watchlist}"})
        put_item(data, item)
        added.append(symbol)
    save_data(data)
    return added, skipped


def remove_symbol(watchlist: str, symbol: str) -> None:
    data = load_data()
    symbol = normalize_symbol(symbol)
    if symbol in data.get("watchlists", {}).get(watchlist, []):
        data["watchlists"][watchlist].remove(symbol)
        item = get_item(data, symbol)
        if item:
            item.timeline.append({"timestamp": utc_now(), "event": "Removed", "details": f"Removed from {watchlist}"})
            put_item(data, item)
        save_data(data)


def get_symbols(watchlist: str) -> List[str]:
    return list(load_data().get("watchlists", {}).get(watchlist, []))


def get_watchlist_item(symbol: str) -> WatchlistItem | None:
    return get_item(load_data(), normalize_symbol(symbol))


def update_watchlist_item(item: WatchlistItem) -> None:
    data = load_data()
    put_item(data, item)
    save_data(data)

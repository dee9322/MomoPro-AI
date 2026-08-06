"""Lightweight startup/page timing helpers."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator, MutableMapping


@contextmanager
def profile_step(store: MutableMapping[str, float], name: str) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        store[name] = round((time.perf_counter() - started) * 1000, 2)

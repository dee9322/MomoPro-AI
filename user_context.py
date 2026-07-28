from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class AppUser:
    id: str
    email: str = ""


_CURRENT_USER: ContextVar[AppUser | None] = ContextVar("momopro_current_user", default=None)


def set_current_user(user_id: str | None, email: str = "") -> None:
    _CURRENT_USER.set(AppUser(str(user_id), str(email or "")) if user_id else None)


def get_current_user() -> AppUser | None:
    return _CURRENT_USER.get()


def current_user_id() -> str | None:
    user = get_current_user()
    return user.id if user else None

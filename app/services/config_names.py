from __future__ import annotations

from threading import Lock


_PENDING: dict[tuple[str, int], str] = {}
_LOCK = Lock()


def set_pending(tenant_id: str, telegram_user_id: int, name: str) -> None:
    with _LOCK:
        _PENDING[(str(tenant_id), int(telegram_user_id))] = name


def peek_pending(tenant_id: str, telegram_user_id: int) -> str | None:
    with _LOCK:
        return _PENDING.get((str(tenant_id), int(telegram_user_id)))


def consume_pending(tenant_id: str, telegram_user_id: int) -> str | None:
    with _LOCK:
        return _PENDING.pop((str(tenant_id), int(telegram_user_id)), None)


def clear_pending(tenant_id: str, telegram_user_id: int) -> None:
    with _LOCK:
        _PENDING.pop((str(tenant_id), int(telegram_user_id)), None)

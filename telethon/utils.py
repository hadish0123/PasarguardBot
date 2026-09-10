"""Small compatibility subset of :mod:`telethon.utils` for Bot API runtime.

The project intentionally uses Telegram's HTTP Bot API and does not depend on
MTProto/API_ID/API_HASH. These helpers cover the utility surface commonly
imported by legacy PasarguardBot modules.
"""
from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any, Iterable, Iterator


def get_display_name(entity: Any) -> str:
    if entity is None:
        return ""
    title = getattr(entity, "title", None)
    if title:
        return str(title)
    first = getattr(entity, "first_name", None) or ""
    last = getattr(entity, "last_name", None) or ""
    name = f"{first} {last}".strip()
    if name:
        return name
    username = getattr(entity, "username", None)
    if username:
        return str(username)
    return str(getattr(entity, "id", ""))


def parse_username(username: str | None) -> tuple[str | None, bool] | None:
    if not username:
        return None
    value = str(username).strip()
    value = re.sub(r"^(?:https?://)?t\.me/", "", value, flags=re.I).strip("/")
    value = value.lstrip("@")
    if not value:
        return None
    return value, False


def resolve_id(peer_id: int) -> tuple[int, type]:
    """Return Telegram's raw ID and a lightweight peer marker class."""
    value = int(peer_id)
    if value < -1000000000000:
        return -value - 1000000000000, type("PeerChannel", (), {})
    if value < 0:
        return -value, type("PeerChat", (), {})
    return value, type("PeerUser", (), {})


def get_peer_id(peer: Any, add_mark: bool = True) -> int:
    value = getattr(peer, "id", peer)
    value = int(value)
    if not add_mark:
        return abs(value)
    name = type(peer).__name__.lower()
    if "channel" in name:
        return -1000000000000 - abs(value)
    if "chat" in name:
        return -abs(value)
    return value


def get_input_peer(entity: Any, allow_self: bool = True, check_hash: bool = True) -> Any:
    """Return an entity unchanged when running through the Bot API layer."""
    return entity


def get_input_user(entity: Any, allow_self: bool = True) -> Any:
    return entity


def get_input_channel(entity: Any, allow_self: bool = True) -> Any:
    return entity


def get_input_chat(entity: Any) -> Any:
    return entity


def chunks(iterable: Iterable[Any], size: int = 100) -> Iterator[list[Any]]:
    if size <= 0:
        raise ValueError("size must be positive")
    batch: list[Any] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def get_appropriated_part_size(file_size: int) -> int:
    size = int(file_size or 0)
    if size <= 10 * 1024 * 1024:
        return 128
    if size <= 100 * 1024 * 1024:
        return 256
    return 512


def split_text(text: str, max_message_len: int = 4096, *args: Any, **kwargs: Any):
    if len(text) <= max_message_len:
        yield text, []
        return
    for start in range(0, len(text), max_message_len):
        yield text[start : start + max_message_len], []

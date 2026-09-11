from __future__ import annotations

import asyncio
import inspect
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import aiohttp

from . import events
from .button import _Button


def _serialize_button(button):
    """Convert both project Bot API buttons and Telethon TL buttons to JSON-safe Bot API dicts."""
    if isinstance(button, dict):
        return {k: _serialize_value(v) for k, v in button.items()}
    if isinstance(button, _Button):
        return _serialize_value(button.to_dict())

    name = button.__class__.__name__
    text = getattr(button, "text", "")
    if name in {"KeyboardButtonCallback", "ButtonCallback"}:
        data = getattr(button, "data", b"")
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        return {"text": text, "callback_data": data}
    if name in {"KeyboardButtonUrl", "ButtonUrl"}:
        return {"text": text, "url": getattr(button, "url", "")}
    if name in {"KeyboardButtonRequestPhone", "ButtonRequestPhone"}:
        return {"text": text, "request_contact": True}
    if name in {"KeyboardButtonRequestGeoLocation", "ButtonRequestGeoLocation"}:
        return {"text": text, "request_location": True}
    if name in {"KeyboardButtonSimpleWebView", "ButtonWebView"}:
        url = getattr(button, "url", None) or getattr(getattr(button, "url", None), "url", None)
        if url:
            return {"text": text, "web_app": {"url": url}}
        return {"text": text}
    if name.startswith("KeyboardButton") or name.startswith("Button"):
        return {"text": text}

    if hasattr(button, "to_dict"):
        try:
            value = button.to_dict()
            return _serialize_value(value)
        except Exception:
            pass
    return _serialize_value(button)


def _serialize_value(value):
    """Recursively convert Telegram/Python values into JSON-safe Bot API values."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, bytearray):
        return bytes(value).decode("utf-8", errors="replace")
    if isinstance(value, memoryview):
        return value.tobytes().decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, _Button):
        return _serialize_value(value.to_dict())
    if hasattr(value, "to_dict"):
        try:
            return _serialize_value(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__class__") and value.__class__.__name__.startswith(("KeyboardButton", "Button")):
        return _serialize_button(value)
    return value


def _button_markup(buttons):
    if not buttons:
        return None
    if isinstance(buttons, dict):
        return _serialize_value(buttons)

    markup_name = buttons.__class__.__name__
    if markup_name in {"ReplyInlineMarkup", "ReplyKeyboardMarkup"}:
        rows = getattr(buttons, "rows", []) or []
        buttons = [getattr(row, "buttons", []) for row in rows]
        if markup_name == "ReplyInlineMarkup":
            return {"inline_keyboard": [[_serialize_button(b) for b in row] for row in buttons]}
        return {"keyboard": [[_serialize_button(b) for b in row] for row in buttons], "resize_keyboard": True}

    if isinstance(buttons, _Button):
        buttons = [[buttons]]
    elif isinstance(buttons, (list, tuple)) and buttons and not isinstance(buttons[0], (list, tuple)):
        buttons = [list(buttons)]

    rows = []
    for row in buttons:
        if hasattr(row, "buttons") and not isinstance(row, (list, tuple)):
            row = row.buttons
        if isinstance(row, _Button):
            row = [row]
        out = []
        for b in row:
            converted = _serialize_button(b)
            if isinstance(converted, dict):
                out.append(converted)
        if out:
            rows.append(out)

    if not rows:
        return None
    inline = all("callback_data" in b or "url" in b for r in rows for b in r)
    return {"inline_keyboard": rows} if inline else {"keyboard": rows, "resize_keyboard": True}


def _chat_id(value):
    return value.id if hasattr(value, "id") else value


class _Message:
    def __init__(self, client, data: dict[str, Any], chat_id=None):
        self._client = client
        self._data = data or {}
        self.id = self._data.get("message_id") or self._data.get("id")
        self.data = b""
        self.text = self._data.get("text") or self._data.get("caption") or ""
        self.raw_text = self.text
        self.message = self
        self.chat_id = chat_id if chat_id is not None else (self._data.get("chat", {}) or {}).get("id")
        self.sender_id = (self._data.get("from", {}) or {}).get("id")
        self.date = self._data.get("date")
        self.out = bool(self._data.get("from", {}) and self._data.get("from", {}).get("is_bot"))
        self.is_private = True
        self.is_channel = False
        self.media = None

    @property
    def client(self):
        return self._client

    async def respond(self, message=None, **kwargs):
        return await self._client.send_message(self.chat_id, message, **kwargs)

    async def reply(self, message=None, **kwargs):
        return await self._client.send_message(self.chat_id, message, reply_to=self.id, **kwargs)

    async def edit(self, message=None, **kwargs):
        return await self._client.edit_message(self.chat_id, self.id, message, **kwargs)

    async def delete(self):
        return await self._client.delete_messages(self.chat_id, [self.id])

    async def get_sender(self):
        sender = self._data.get("from") or {}
        return SimpleNamespace(**sender)

    async def download_media(self, *args, **kwargs):
        return await self._client.download_media(self, *args, **kwargs)


class TelegramClient:
    def __init__(self, session=None, api_id=None, api_hash=None, bot_token=None, **kwargs):
        self._token = bot_token or kwargs.get("token") or ""
        self._handlers = []
        self._session = None
        self._me = None
        self._chat_locks = {}
        self._dispatch_tasks = set()

    def add_event_handler(self, callback, builder=None):
        self._handlers.append((callback, builder))

    def remove_event_handler(self, callback, builder=None):
        self._handlers = [(cb, b) for cb, b in self._handlers if cb != callback or (builder is not None and b != builder)]

    async def start(self, *args, **kwargs):
        timeout = aiohttp.ClientTimeout(total=65)
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30, ttl_dns_cache=300, enable_cleanup_closed=True)
        self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        self._me = await self._api("getMe")
        return self

    async def disconnect(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def _dispatch_update_guarded(self, update):
        try:
            return await self._dispatch(update)
        except events.StopPropagation:
            raise
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Unhandled update dispatch error")

    async def _dispatch(self, update):
        chat_id = getattr(update, "chat_id", None) or getattr(update, "sender_id", None) or 0
        lock = self._chat_locks.setdefault(chat_id, asyncio.Lock())
        async with lock:
            return await self._dispatch_inner(update)

    async def _dispatch_inner(self, update):
        if not self._handlers:
            return
        handlers = sorted(self._handlers, key=lambda item: getattr(item[0], "_handler_priority", 0))
        for callback, builder in handlers:
            try:
                if builder is not None and hasattr(builder, "matches") and not await builder.matches(update):
                    continue
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Handler filter failed for %s: %s", builder.__class__.__name__ if builder else "unknown", exc)
                continue
            result = callback(update)
            if inspect.isawaitable(result):
                await result

    async def _api(self, method, **params):
        if not self._session:
            raise RuntimeError("Telegram client is not started")
        clean = {k: _serialize_value(v) for k, v in params.items() if v is not None}
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        async with self._session.post(url, json=clean, timeout=aiohttp.ClientTimeout(total=65)) as response:
            payload = await response.json(content_type=None)
            if not payload.get("ok"):
                raise RuntimeError(payload.get("description", f"Telegram API error: {method}"))
            return payload.get("result")

    async def get_me(self):
        return SimpleNamespace(**(self._me or await self._api("getMe")))

    async def send_message(self, entity=None, message=None, **kwargs):
        params = {"chat_id": _chat_id(entity), "text": message or ""}
        if kwargs.get("parse_mode"):
            params["parse_mode"] = "HTML" if str(kwargs["parse_mode"]).lower() == "html" else "Markdown"
        if "buttons" in kwargs:
            params["reply_markup"] = _button_markup(kwargs["buttons"])
        if kwargs.get("reply_to"):
            params["reply_parameters"] = {"message_id": getattr(kwargs["reply_to"], "id", kwargs["reply_to"])}
        result = await self._api("sendMessage", **params)
        return _Message(self, result, params["chat_id"])

    async def edit_message(self, entity, message, text=None, **kwargs):
        params = {"chat_id": _chat_id(entity), "message_id": getattr(message, "id", message), "text": text or ""}
        if kwargs.get("parse_mode"):
            params["parse_mode"] = "HTML" if str(kwargs["parse_mode"]).lower() == "html" else "Markdown"
        if "buttons" in kwargs:
            params["reply_markup"] = _button_markup(kwargs["buttons"])
        result = await self._api("editMessageText", **params)
        return _Message(self, result, params["chat_id"]) if isinstance(result, dict) else result

    async def delete_messages(self, entity, message_ids):
        for mid in message_ids if isinstance(message_ids, (list, tuple)) else [message_ids]:
            await self._api("deleteMessage", chat_id=_chat_id(entity), message_id=getattr(mid, "id", mid))
        return True

    async def get_messages(self, entity, ids=None, limit=1, **kwargs):
        return None if ids is not None else []

    async def iter_messages(self, *args, **kwargs):
        return
        yield

    async def send_file(self, entity, file, caption=None, **kwargs):
        path = Path(file) if isinstance(file, (str, os.PathLike)) else None
        method, field = "sendDocument", "document"
        if path and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            method, field = "sendPhoto", "photo"
        data = aiohttp.FormData()
        data.add_field("chat_id", str(_chat_id(entity)))
        if caption:
            data.add_field("caption", caption)
        if path:
            data.add_field(field, path.open("rb"), filename=path.name)
        else:
            data.add_field(field, str(file))
        if self._session is None:
            raise RuntimeError("Telegram client is not started")
        async with self._session.post(f"https://api.telegram.org/bot{self._token}/{method}", data=data) as response:
            payload = await response.json(content_type=None)
        if not payload.get("ok"):
            raise RuntimeError(payload.get("description", "Telegram upload failed"))
        return _Message(self, payload.get("result", {}), _chat_id(entity))

    async def download_media(self, message, file=None, **kwargs):
        return None

    async def get_entity(self, entity):
        return SimpleNamespace(id=_chat_id(entity), username=None)

    async def get_participants(self, *args, **kwargs):
        return []

    async def forward_messages(self, entity, messages, from_peer=None, **kwargs):
        return None

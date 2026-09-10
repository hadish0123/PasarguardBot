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


def _button_markup(buttons):
    if not buttons:
        return None
    if isinstance(buttons, dict):
        return buttons
    if isinstance(buttons, _Button):
        buttons = [[buttons]]
    elif isinstance(buttons, (list, tuple)) and buttons and not isinstance(buttons[0], (list, tuple)):
        buttons = [list(buttons)]
    rows = []
    for row in buttons:
        if isinstance(row, _Button):
            row = [row]
        out = []
        for b in row:
            if isinstance(b, dict):
                out.append(b)
            elif hasattr(b, "to_dict"):
                out.append(b.to_dict())
        if out:
            rows.append(out)
    return {"inline_keyboard": rows} if rows and all("callback_data" in b or "url" in b for r in rows for b in r) else {"keyboard": rows, "resize_keyboard": True}


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
        self.entities = self._data.get("entities", [])
        self.media = self._data.get("photo") or self._data.get("document") or self._data.get("video")
        self.file = self.media
        chat_type = (self._data.get("chat", {}) or {}).get("type")
        self.is_private = chat_type == "private"
        self.is_channel = chat_type == "channel"
        self.is_group = chat_type in {"group", "supergroup"}
        self.incoming = True
        self.out = False

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(name)

    async def reply(self, message=None, **kwargs):
        return await self._client.send_message(self.chat_id, message or "", **kwargs)

    async def respond(self, message=None, **kwargs):
        return await self.reply(message, **kwargs)

    async def edit(self, text=None, **kwargs):
        return await self._client.edit_message(self.chat_id, self.id, text or "", **kwargs)

    async def delete(self, *args, **kwargs):
        return await self._client.delete_messages(self.chat_id, [self.id])

    async def get_reply_message(self):
        reply_id = (self._data.get("reply_to_message") or {}).get("message_id")
        return await self._client.get_messages(self.chat_id, ids=reply_id) if reply_id else None

    async def download_media(self, file=None, **kwargs):
        return await self._client.download_media(self, file=file, **kwargs)


class _CallbackEvent:
    def __init__(self, client, update):
        self._client = client
        self._query = update.get("callback_query", {})
        self.id = self._query.get("id")
        self.data = (self._query.get("data") or "").encode()
        self.text = self.raw_text = ""
        self.sender_id = (self._query.get("from") or {}).get("id")
        self.chat_id = ((self._query.get("message") or {}).get("chat") or {}).get("id")
        self.message = _Message(client, self._query.get("message") or {}, self.chat_id) if self._query.get("message") else None
        self.original_update = SimpleNamespace(msg_id=getattr(self.message, "id", None))
        self.incoming = True
        self.is_private = bool(self.message and self.message.is_private)
        self.is_channel = bool(self.message and self.message.is_channel)
        self.is_group = bool(self.message and self.message.is_group)

    async def answer(self, message=None, alert=False, **kwargs):
        return await self._client._api("answerCallbackQuery", callback_query_id=self.id, text=message or "", show_alert=alert)

    async def edit(self, text=None, **kwargs):
        return await self._client.edit_message(self.chat_id, self.message.id, text or "", **kwargs) if self.message else None

    async def delete(self):
        return await self._client.delete_messages(self.chat_id, [self.message.id]) if self.message else None

    async def get_message(self):
        return self.message


class TelegramClient:
    def __init__(self, *args, **kwargs):
        self.parse_mode = "html"
        self._token = None
        self._handlers: list[tuple[Any, Any]] = []
        self._session: aiohttp.ClientSession | None = None
        self._offset = 0
        self._stop = asyncio.Event()
        self._me = None
        self._runtime_context_factory = None

    def add_event_handler(self, callback, event=None):
        self._handlers.append((callback, event))
        return callback

    def on(self, event=None):
        def decorator(callback):
            self.add_event_handler(callback, event)
            return callback
        return decorator

    def clone_handlers_from(self, source: "TelegramClient") -> None:
        self._handlers = list(source._handlers)

    def set_runtime_context_factory(self, factory) -> None:
        self._runtime_context_factory = factory

    def is_connected(self) -> bool:
        return bool(self._session and not self._session.closed and not self._stop.is_set())

    @property
    def disconnected(self):
        return self._wait_disconnected()

    async def _wait_disconnected(self):
        await self._stop.wait()

    async def start(self, *args, bot_token=None, **kwargs):
        self._token = bot_token or os.getenv("BOT_TOKEN")
        if not self._token:
            raise ValueError("BOT_TOKEN is required")
        self._session = aiohttp.ClientSession()
        self._stop.clear()
        self._offset = 0
        self._me = await self._api("getMe")
        await self._api("deleteWebhook", drop_pending_updates=False)
        return self

    async def disconnect(self):
        self._stop.set()
        if self._session and not self._session.closed:
            await self._session.close()

    async def run_until_disconnected(self):
        while not self._stop.is_set():
            try:
                updates = await self._api("getUpdates", offset=self._offset, timeout=30, allowed_updates=["message", "callback_query", "edited_message", "chat_member", "my_chat_member"])
                for update in updates or []:
                    self._offset = int(update.get("update_id", 0)) + 1
                    try:
                        await self._dispatch(update)
                    except events.StopPropagation:
                        continue
                    except Exception:
                        import logging
                        logging.getLogger(__name__).exception("Telegram update handler failed")
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(2)

    async def _dispatch(self, update):
        if self._runtime_context_factory is not None:
            from app.runtime.context import tenant_context
            tenant = self._runtime_context_factory()
            if tenant is not None:
                with tenant_context(tenant):
                    return await self._dispatch_inner(update)
        return await self._dispatch_inner(update)

    async def _dispatch_inner(self, update):
        if "callback_query" in update:
            event = _CallbackEvent(self, update)
        elif "message" in update:
            event = _Message(self, update["message"])
            event.original_update = SimpleNamespace(msg_id=event.id)
        else:
            return
        handlers = sorted(self._handlers, key=lambda item: getattr(item[0], "_handler_priority", 0))
        for callback, builder in handlers:
            try:
                if builder is not None and hasattr(builder, "matches") and not await builder.matches(event):
                    continue
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Handler filter failed for %s: %s", builder.__class__.__name__ if builder else "unknown", exc)
                continue
            result = callback(event)
            if inspect.isawaitable(result):
                await result

    async def _api(self, method, **params):
        if not self._session:
            raise RuntimeError("Telegram client is not started")
        clean = {k: v for k, v in params.items() if v is not None}
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        async with self._session.post(url, json=clean, timeout=aiohttp.ClientTimeout(total=60)) as response:
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
        mids = [getattr(m, "id", m) for m in (messages if isinstance(messages, (list, tuple)) else [messages])]
        return await self._api("forwardMessages", chat_id=_chat_id(entity), from_chat_id=_chat_id(from_peer), message_ids=mids)

    async def pin_message(self, entity, message, **kwargs):
        return await self._api("pinChatMessage", chat_id=_chat_id(entity), message_id=getattr(message, "id", message), disable_notification=kwargs.get("notify", True) is False)

    async def unpin_message(self, entity, message=None, **kwargs):
        params = {"chat_id": _chat_id(entity)}
        if message is not None:
            params["message_id"] = getattr(message, "id", message)
        return await self._api("unpinChatMessage", **params)

    async def send_read_acknowledge(self, *args, **kwargs):
        return True

    async def __call__(self, request, *args, **kwargs):
        raise NotImplementedError("MTProto request objects are not supported; use Telegram Bot API methods")

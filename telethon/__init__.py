from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import aiohttp

from . import events

logger = logging.getLogger(__name__)


class Button:
    def __init__(self, text: str, *, callback_data: bytes | None = None, url: str | None = None):
        self.text = text
        self.callback_data = callback_data
        self.url = url

    @classmethod
    def inline(cls, text: str, data: bytes | str):
        if isinstance(data, str):
            data = data.encode("utf-8")
        return cls(text, callback_data=data)

    @classmethod
    def url(cls, text: str, url: str):
        return cls(text, url=url)

    @classmethod
    def text(cls, text: str):
        return cls(text)


class _PatternMatch:
    def __init__(self, pattern: str, text: str):
        self._match = re.search(pattern, text)

    def group(self, *args):
        if self._match is None:
            return None
        return self._match.group(*args)

    def __bool__(self):
        return self._match is not None


@dataclass(slots=True)
class _Sender:
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    phone: str | None = None


class _Message:
    def __init__(self, payload: dict[str, Any], event: "_Event"):
        self._payload = payload
        self._event = event
        self.id = payload.get("message_id") or payload.get("id")
        self.message = payload.get("text") or payload.get("caption") or ""
        self.text = self.message
        self.raw_text = self.message
        self.chat_id = event.chat_id
        self.sender_id = event.sender_id

    async def delete(self):
        return await self._event.delete()


class _Event:
    def __init__(self, client: "TelegramClient", update: dict[str, Any], *, callback: bool = False):
        self.client = client
        self._update = update
        self._callback = callback
        if callback:
            cb = update["callback_query"]
            self.data = (cb.get("data") or "").encode("utf-8")
            self.id = cb.get("id")
            message = cb.get("message") or {}
            self._message_payload = message
            self._user = cb.get("from") or {}
        else:
            message = update.get("message") or update.get("edited_message") or update.get("channel_post") or {}
            self._message_payload = message
            self.data = b""
            self.id = update.get("update_id")
            self._user = message.get("from") or {}
        chat = self._message_payload.get("chat") or {}
        self.chat_id = chat.get("id")
        self.sender_id = self._user.get("id")
        self.is_private = chat.get("type") == "private"
        self.is_incoming = True
        self.raw_text = self._message_payload.get("text") or self._message_payload.get("caption") or ""
        self.message = _Message(self._message_payload, self) if self._message_payload else None
        self.pattern_match = None

    async def get_sender(self):
        return _Sender(
            id=int(self._user.get("id", 0)),
            first_name=self._user.get("first_name"),
            last_name=self._user.get("last_name"),
            username=self._user.get("username"),
        )

    async def respond(self, text: str = "", *, buttons=None, **kwargs):
        return await self.client.send_message(self.chat_id, text, buttons=buttons, **kwargs)

    async def reply(self, text: str = "", *, buttons=None, **kwargs):
        return await self.respond(text, buttons=buttons, **kwargs)

    async def edit(self, text: str = "", *, buttons=None, **kwargs):
        if self._callback and self._message_payload.get("message_id"):
            return await self.client.edit_message(
                self.chat_id,
                self._message_payload["message_id"],
                text,
                buttons=buttons,
                **kwargs,
            )
        if self.message and self.message.id:
            return await self.client.edit_message(self.chat_id, self.message.id, text, buttons=buttons, **kwargs)
        return None

    async def delete(self):
        message_id = self._message_payload.get("message_id")
        if message_id:
            return await self.client.delete_messages(self.chat_id, message_id)
        return None

    async def answer(self, text: str | None = None, **kwargs):
        if not self._callback or not self.id:
            return True
        return await self.client._request(
            "answerCallbackQuery",
            {"callback_query_id": self.id, **({"text": text} if text else {})},
        )


class TelegramClient:
    """Small Telethon-compatible facade backed exclusively by Telegram Bot API.

    It intentionally implements only the API surface used by this project, so
    application handlers keep their existing structure while API_ID/API_HASH
    are no longer required.
    """

    def __init__(self, session: str, api_id: int | None = None, api_hash: str | None = None, **_: Any):
        self.session = session
        self.api_id = api_id
        self.api_hash = api_hash
        self._token: str | None = None
        self._base_url: str | None = None
        self._session: aiohttp.ClientSession | None = None
        self._handlers: list[tuple[Any, Any]] = []
        self._stop = asyncio.Event()
        self._me: _Sender | None = None

    def add_event_handler(self, callback, event):
        self._handlers.append((callback, event))

    async def start(self, *, bot_token: str | None = None, **kwargs):
        token = bot_token or self._token
        if not token:
            raise RuntimeError("BOT_TOKEN is required")
        self._token = token
        self._base_url = f"https://api.telegram.org/bot{token}"
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=35))
        me = await self._request("getMe")
        self._me = _Sender(
            id=int(me["id"]), first_name=me.get("first_name"), username=me.get("username")
        )
        return self

    async def _request(self, method: str, payload: dict[str, Any] | None = None):
        if not self._session or not self._base_url:
            raise RuntimeError("Telegram client is not started")
        async with self._session.post(f"{self._base_url}/{method}", json=payload or {}) as response:
            data = await response.json(content_type=None)
            if not data.get("ok"):
                raise RuntimeError(f"Telegram Bot API {method} failed: {data.get('description', data)}")
            return data.get("result")

    @staticmethod
    def _keyboard(buttons):
        if not buttons:
            return None
        rows = []
        for row in buttons:
            row_out = []
            for button in row if isinstance(row, (list, tuple)) else [row]:
                if isinstance(button, Button):
                    item = {"text": button.text}
                    if button.callback_data is not None:
                        item["callback_data"] = button.callback_data.decode("utf-8", errors="replace")
                    elif button.url:
                        item["url"] = button.url
                    row_out.append(item)
                elif isinstance(button, dict):
                    row_out.append(button)
            if row_out:
                rows.append(row_out)
        return {"inline_keyboard": rows} if rows else None

    async def send_message(self, entity, message: str = "", *, buttons=None, **kwargs):
        payload = {"chat_id": entity, "text": message}
        keyboard = self._keyboard(buttons)
        if keyboard:
            payload["reply_markup"] = keyboard
        if kwargs.get("parse_mode"):
            payload["parse_mode"] = kwargs["parse_mode"]
        else:
            payload["parse_mode"] = "Markdown"
        return await self._request("sendMessage", payload)

    async def edit_message(self, entity, message_id: int, text: str, *, buttons=None, **kwargs):
        payload = {"chat_id": entity, "message_id": message_id, "text": text, "parse_mode": kwargs.get("parse_mode", "Markdown")}
        keyboard = self._keyboard(buttons)
        if keyboard:
            payload["reply_markup"] = keyboard
        return await self._request("editMessageText", payload)

    async def delete_messages(self, entity, message_ids):
        if isinstance(message_ids, (list, tuple)):
            return [await self._request("deleteMessage", {"chat_id": entity, "message_id": mid}) for mid in message_ids]
        return await self._request("deleteMessage", {"chat_id": entity, "message_id": message_ids})

    async def get_me(self):
        result = await self._request("getMe")
        return _Sender(id=int(result["id"]), first_name=result.get("first_name"), username=result.get("username"))

    async def run_until_disconnected(self):
        offset = 0
        while not self._stop.is_set():
            try:
                updates = await self._request("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message", "callback_query"]})
                for update in updates or []:
                    offset = max(offset, int(update["update_id"]) + 1)
                    await self._dispatch(update)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telegram Bot API polling failed")
                await asyncio.sleep(2)

    async def _dispatch(self, update):
        is_callback = "callback_query" in update
        event = _Event(self, update, callback=is_callback)
        for callback, builder in list(self._handlers):
            try:
                if hasattr(builder, "matches") and not builder.matches(event):
                    continue
                if isinstance(builder, events.NewMessage) and builder.pattern:
                    event.pattern_match = _PatternMatch(builder.pattern, event.raw_text)
                await callback(event)
            except Exception:
                logger.exception("Telegram handler failed: %r", callback)

    async def disconnect(self):
        self._stop.set()
        if self._session and not self._session.closed:
            await self._session.close()
        return True


__all__ = ["Button", "TelegramClient", "events"]

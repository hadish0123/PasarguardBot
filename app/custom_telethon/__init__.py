"""PasarguardBot's Telegram Bot API compatibility runtime.

This is intentionally not a package named ``telethon``.  The real Telethon
package remains available for modules that need its utility/TL/error surface,
while this small runtime keeps the application's HTTP Bot API client and
legacy event-filter semantics without API_ID/API_HASH/session credentials.
"""
from .bot import TelegramClient, _Message
from . import events
from .button import Button

_original_message_getattribute = _Message.__getattribute__


def _message_getattribute(self, name):
    if name == "message":
        return self
    return _original_message_getattribute(self, name)


_Message.__getattribute__ = _message_getattribute


def _is_connected(self):
    return bool(self._session and not self._session.closed and not self._stop.is_set())


async def _disconnected(self):
    await self._stop.wait()


TelegramClient.is_connected = _is_connected
TelegramClient.disconnected = property(lambda self: _disconnected(self))

_original_send_message = TelegramClient.send_message


async def _send_message(self, entity=None, message=None, **kwargs):
    kwargs.setdefault("parse_mode", "Markdown")
    return await _original_send_message(self, entity=entity, message=message, **kwargs)


TelegramClient.send_message = _send_message

_original_edit_message = TelegramClient.edit_message


async def _edit_message(self, entity, message, text=None, **kwargs):
    kwargs.setdefault("parse_mode", "Markdown")
    return await _original_edit_message(self, entity, message, text, **kwargs)


TelegramClient.edit_message = _edit_message

__all__ = ["TelegramClient", "events", "Button"]

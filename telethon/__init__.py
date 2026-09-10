"""Small Bot API compatibility layer used by PasarguardBot.

This project intentionally does not use Telegram MTProto/API credentials.
All network traffic goes through Telegram's HTTP Bot API using BOT_TOKEN only.
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

__all__ = ["TelegramClient", "events", "Button"]

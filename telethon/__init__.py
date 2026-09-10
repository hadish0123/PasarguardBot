"""Small Bot API compatibility layer used by PasarguardBot.

This project intentionally does not use Telegram MTProto/API credentials.
All network traffic goes through Telegram's HTTP Bot API using BOT_TOKEN only.
"""
from .bot import TelegramClient, _Message
from . import events
from .button import Button

# Legacy handlers expect Telethon's NewMessage event.message object. The
# compatibility message already exposes .text/.raw_text, so make .message
# resolve to the message object itself while preserving .text for content.
_original_message_getattribute = _Message.__getattribute__
def _message_getattribute(self, name):
    if name == "message":
        return self
    return _original_message_getattribute(self, name)
_Message.__getattribute__ = _message_getattribute

__all__ = ["TelegramClient", "events", "Button"]

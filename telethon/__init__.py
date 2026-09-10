"""Small Bot API compatibility layer used by PasarguardBot.

This project intentionally does not use Telegram MTProto/Telethon credentials.
The compatibility surface keeps the existing handler modules working while all
network traffic goes through Telegram's HTTP Bot API using BOT_TOKEN only.
"""
from .bot import TelegramClient
from . import events
from .button import Button

__all__ = ["TelegramClient", "events", "Button"]

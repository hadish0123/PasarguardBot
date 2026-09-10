"""Telegram runtime for PasarguardBot.

The project now uses Telegram's HTTP Bot API. BOT_TOKEN and ADMIN_ID are the
only Telegram credentials required; API_ID/API_HASH and MTProto sessions are
not used.
"""
from telethon import TelegramClient
from telethon.extensions import markdown
from telethon.extensions.markdown import DEFAULT_DELIMITERS
from telethon.tl.types import (
    MessageEntityBlockquote,
    MessageEntityCustomEmoji,
    MessageEntitySpoiler,
    MessageEntityTextUrl,
)

from config import BOT_TOKEN

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required!")


DEFAULT_DELIMITERS["^q^"] = lambda *a, **k: MessageEntityBlockquote(*a, **k, collapsed=False)
DEFAULT_DELIMITERS["^qc^"] = lambda *a, **k: MessageEntityBlockquote(*a, **k, collapsed=True)
DEFAULT_DELIMITERS["^sp^"] = lambda *a, **k: MessageEntitySpoiler(*a, **k)


class CustomMarkdown:
    """Legacy parser surface retained for modules that import it."""

    @staticmethod
    def parse(text):
        return markdown.parse(text)

    @staticmethod
    def unparse(text, entities):
        return markdown.unparse(text, entities)


Kenzo = TelegramClient()
Kenzo.parse_mode = "Markdown"

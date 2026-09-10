"""Telegram runtime for PasarguardBot.

The application runtime uses Telegram's HTTP Bot API. BOT_TOKEN and ADMIN_ID
remain the only Telegram credentials required by the bot runtime; API_ID,
API_HASH and MTProto sessions are not used by the application client.

The real PyPI Telethon package is intentionally kept available for modules
that import its utilities, TL types, errors, and request definitions. The
small Bot API compatibility client/events/buttons live under
``app.custom_telethon`` so they no longer shadow the real ``telethon`` package.
Legacy project-local TL helper types are installed centrally by
``app._telethon_patch`` before Telegram plugins are imported.
"""

import telethon as _telethon
from app import _telethon_patch as _telethon_patch  # noqa: F401
from app.custom_telethon import Button as BotAPIButton
from app.custom_telethon import TelegramClient
from app.custom_telethon import events as BotAPIEvents

# Preserve the existing plugin surface that expects ``from telethon import
# events, Button`` while keeping every other Telethon module backed by the
# real PyPI package. This is an API-level compatibility bridge, not an import
# shadowing package.
_telethon.events = BotAPIEvents
_telethon.Button = BotAPIButton

try:
    from telethon.tl import custom as _telethon_custom

    _telethon_custom.Button = BotAPIButton
except Exception:
    # Import-time compatibility must not prevent the real Telethon package
    # from being used for its normal modules.
    pass

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


class RuntimeAwareTelegramClient(TelegramClient):
    """Route legacy global ``Kenzo`` API calls to the active tenant client.

    Most existing plugins import ``Kenzo`` directly at module import time.
    Representative runtimes reuse those handlers, so a direct ``Kenzo`` call
    would otherwise send through the central bot token. During a representative
    update the manager installs the current client in a context variable; this
    facade transparently routes Telegram API calls to that client while keeping
    central-bot behavior unchanged outside a representative runtime.
    """

    _ROUTED_METHODS = frozenset(
        {
            "send_message",
            "edit_message",
            "delete_messages",
            "get_messages",
            "iter_messages",
            "send_file",
            "download_media",
            "get_entity",
            "get_participants",
            "forward_messages",
            "pin_message",
            "unpin_message",
            "send_read_acknowledge",
            "get_me",
        }
    )

    def __getattribute__(self, name):
        if name in RuntimeAwareTelegramClient._ROUTED_METHODS:
            from app.runtime.context import get_current_client

            current = get_current_client()
            if current is not None and current is not self:
                return getattr(current, name)
        return super().__getattribute__(name)


class CustomMarkdown:
    """Legacy parser surface retained for modules that import it."""

    @staticmethod
    def parse(text):
        return markdown.parse(text)

    @staticmethod
    def unparse(text, entities):
        return markdown.unparse(text, entities)


Kenzo = RuntimeAwareTelegramClient()
Kenzo.parse_mode = "Markdown"

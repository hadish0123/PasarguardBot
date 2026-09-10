"""Telegram runtime for PasarguardBot.

The application runtime uses Telegram's HTTP Bot API. BOT_TOKEN and ADMIN_ID
remain the only Telegram credentials required by the bot runtime; API_ID,
API_HASH and MTProto sessions are not used by the application client.

The real PyPI Telethon package is intentionally kept available for modules
that import its utilities, TL types, errors, and request definitions. The
small Bot API compatibility client/events/buttons live under
``app.custom_telethon`` so they no longer shadow the real ``telethon`` package.
The legacy project-local TL helper types live under ``app.telethon_patched``.
"""

import telethon as _telethon
from app.custom_telethon import Button as BotAPIButton
from app.custom_telethon import TelegramClient
from app.custom_telethon import events as BotAPIEvents
from app.telethon_patched.tl import types as _patched_types

# Preserve the existing plugin surface that expects ``from telethon import
# events, Button`` while keeping every other Telethon module backed by the
# real PyPI package. This is an API-level compatibility bridge, not an import
# shadowing package.
_telethon.events = BotAPIEvents
_telethon.Button = BotAPIButton

# The former project-local Telethon fork supplied additional lightweight TL
# names which do not exist in the PyPI package. Expose those names on the real
# module after importing the explicit project-local implementation, so legacy
# plugin imports continue to work without restoring a top-level ``telethon``
# package that would shadow PyPI Telethon.
try:
    from telethon.tl import custom as _telethon_custom

    _telethon_custom.Button = BotAPIButton
except Exception:
    # Import-time compatibility must not prevent the real Telethon package
    # from being used for its normal modules.
    pass

try:
    from telethon.tl import types as _real_types

    for _name in (
        "ButtonTypeDefault",
        "KeyboardInlineButtonRow",
        "InlineButtonTypeCallback",
    ):
        if not hasattr(_real_types, _name):
            setattr(_real_types, _name, getattr(_patched_types, _name))
except Exception:
    # Keep normal Telethon imports independent from this compatibility bridge.
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

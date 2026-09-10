"""Project-local compatibility layer for legacy Telegram TL helper types.

This package is intentionally separate from the real PyPI ``telethon`` package.
It contains only the lightweight compatibility objects that the PasarguardBot
codebase historically imported from its old top-level telethon fork.
"""

from .tl.types import (
    ButtonTypeDefault,
    KeyboardInlineButtonRow,
    InlineButtonTypeCallback,
)

__all__ = [
    "ButtonTypeDefault",
    "KeyboardInlineButtonRow",
    "InlineButtonTypeCallback",
]

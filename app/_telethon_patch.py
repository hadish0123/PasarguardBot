"""Central compatibility patch for legacy project-local Telethon TL names.

The old project fork exposed lightweight TL classes that are not part of the
official PyPI Telethon package. Keep the real Telethon package intact and
install the legacy names directly on ``telethon.tl.types`` before any
``app.telegram`` module can import them.
"""

from __future__ import annotations

import telethon.tl.types as _tl_types


class _LegacyTLObject:
    """Small compatibility object matching the historical fork behavior."""

    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)
        if args:
            self.args = args

    def to_dict(self):
        return dict(self.__dict__)


def _legacy_type(name: str):
    cls = type(name, (_LegacyTLObject,), {"__module__": _tl_types.__name__})
    setattr(_tl_types, name, cls)
    return cls


for _name in (
    "ButtonTypeSimpleWebView",
    "InlineButtonTypeCopy",
    "ButtonTypeDefault",
    "KeyboardInlineButtonRow",
    "InlineButtonTypeCallback",
):
    if not hasattr(_tl_types, _name):
        _legacy_type(_name)


_previous_getattr = getattr(_tl_types, "__getattr__", None)


def _patched_getattr(name: str):
    if name.startswith("__"):
        raise AttributeError(name)
    if _previous_getattr is not None:
        try:
            return _previous_getattr(name)
        except AttributeError:
            pass
    return _legacy_type(name)


_tl_types.__getattr__ = _patched_getattr

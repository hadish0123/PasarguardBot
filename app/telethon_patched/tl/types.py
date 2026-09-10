"""Compatibility TL types from the former project-local Telethon fork.

The old top-level ``telethon/tl/types.py`` intentionally generated lightweight
classes for legacy names instead of implementing MTProto schema objects. Keep
that behavior here without shadowing the real PyPI Telethon package.
"""

class _TLObject:
    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)
        if args:
            self.args = args

    def to_dict(self):
        return dict(self.__dict__)


class ButtonTypeDefault(_TLObject):
    pass


class KeyboardInlineButtonRow(_TLObject):
    pass


class InlineButtonTypeCallback(_TLObject):
    pass


def __getattr__(name):
    """Preserve the old fork's permissive compatibility behavior."""
    if name.startswith("__"):
        raise AttributeError(name)
    cls = type(name, (_TLObject,), {})
    globals()[name] = cls
    return cls

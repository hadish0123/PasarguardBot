from __future__ import annotations

import re


class StopPropagation(Exception):
    pass


class _Builder:
    def __init__(self, *args, incoming=None, func=None, pattern=None, data=None, **kwargs):
        self.incoming = incoming
        self.func = func
        self.pattern = pattern
        self.data = data

    async def matches(self, event):
        if self.incoming is not None and getattr(event, "incoming", True) != self.incoming:
            return False
        if self.pattern is not None:
            text = getattr(event, "raw_text", None) or getattr(event, "text", "") or ""
            if re.match(self.pattern, text) is None:
                return False
        if self.data is not None:
            actual = getattr(event, "data", b"")
            expected = self.data
            if isinstance(expected, bytes):
                if isinstance(actual, str):
                    actual = actual.encode()
                if hasattr(expected, "match"):
                    if expected.match(actual) is None:
                        return False
                elif actual != expected:
                    return False
            else:
                if isinstance(actual, bytes):
                    actual = actual.decode(errors="ignore")
                if hasattr(expected, "match"):
                    if expected.match(actual) is None:
                        return False
                elif actual != expected:
                    return False
        if self.func is not None:
            result = self.func(event)
            if hasattr(result, "__await__"):
                result = await result
            return bool(result)
        return True


class NewMessage(_Builder):
    pass


class CallbackQuery(_Builder):
    pass


class ChatAction(_Builder):
    pass


class Raw(_Builder):
    pass


NewMessage.Event = object
CallbackQuery.Event = object
ChatAction.Event = object

from __future__ import annotations

import re


class StopPropagation(Exception):
    pass


class _Builder:
    def __init__(self, *args, incoming=None, outgoing=None, func=None, pattern=None, data=None, chats=None,
                 from_users=None, blacklist_chats=False, **kwargs):
        self.incoming = incoming
        self.outgoing = outgoing
        self.func = func
        self.pattern = pattern
        self.data = data
        self.chats = chats
        self.from_users = from_users
        self.blacklist_chats = blacklist_chats

    @staticmethod
    def _ids(value):
        if value is None:
            return set()
        if isinstance(value, (list, tuple, set, frozenset)):
            return {getattr(v, "id", v) for v in value}
        return {getattr(value, "id", value)}

    @staticmethod
    def _match_regex(pattern, text: str) -> bool:
        if hasattr(pattern, "match"):
            raw_pattern = getattr(pattern, "pattern", None)
            target = text.encode() if isinstance(raw_pattern, bytes) else text
            return pattern.match(target) is not None
        if isinstance(pattern, bytes):
            return re.match(pattern, text.encode()) is not None
        return re.match(pattern, text) is not None

    async def matches(self, event):
        if self.incoming is not None and getattr(event, "incoming", True) != self.incoming:
            return False
        if self.outgoing is not None and getattr(event, "out", False) != self.outgoing:
            return False
        if self.chats is not None:
            chat_id = getattr(event, "chat_id", None)
            in_chats = chat_id in self._ids(self.chats)
            if self.blacklist_chats:
                if in_chats:
                    return False
            elif not in_chats:
                return False
        if self.from_users is not None and getattr(event, "sender_id", None) not in self._ids(self.from_users):
            return False
        if self.pattern is not None:
            text = getattr(event, "raw_text", None) or getattr(event, "text", "") or ""
            if not isinstance(text, str):
                text = str(text) if text else ""
            if not self._match_regex(self.pattern, text):
                return False
        if self.data is not None:
            actual = getattr(event, "data", b"")
            expected = self.data
            if hasattr(expected, "match"):
                raw_pattern = getattr(expected, "pattern", None)
                target = actual if isinstance(raw_pattern, bytes) else (actual.decode(errors="ignore") if isinstance(actual, bytes) else actual)
                if expected.match(target) is None:
                    return False
            elif isinstance(expected, bytes):
                if isinstance(actual, str):
                    actual = actual.encode()
                if actual != expected:
                    return False
            else:
                if isinstance(actual, bytes):
                    actual = actual.decode(errors="ignore")
                if actual != expected:
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

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class NewMessage:
    pattern: str | None = None
    incoming: bool | None = None

    def matches(self, event: Any) -> bool:
        if self.incoming is True and not getattr(event, "is_incoming", True):
            return False
        if self.pattern is not None:
            return re.search(self.pattern, getattr(event, "raw_text", "")) is not None
        return True


@dataclass(slots=True)
class CallbackQuery:
    data: bytes | str | Any | None = None

    def matches(self, event: Any) -> bool:
        if self.data is None:
            return True

        actual = getattr(event, "data", b"")
        expected = self.data.encode() if isinstance(self.data, str) else self.data

        # Support both exact callback data and regex/pattern matchers. The
        # application uses compiled regexes for namespaced callback routers;
        # comparing the regex object directly to bytes can never match.
        if hasattr(expected, "search"):
            try:
                return bool(expected.search(actual))
            except TypeError:
                try:
                    return bool(expected.search(actual.decode("utf-8", errors="replace")))
                except (AttributeError, UnicodeDecodeError):
                    return False

        if isinstance(actual, str):
            actual = actual.encode("utf-8")
        return actual == expected

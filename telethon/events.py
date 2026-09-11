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
    data: bytes | str | None = None

    def matches(self, event: Any) -> bool:
        if self.data is None:
            return True
        actual = getattr(event, "data", b"")
        expected = self.data.encode() if isinstance(self.data, str) else self.data
        return actual == expected

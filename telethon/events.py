from __future__ import annotations

class StopPropagation(Exception):
    pass

class _Builder:
    def __init__(self, *args, incoming=None, func=None, **kwargs):
        self.incoming = incoming
        self.func = func

    async def matches(self, event):
        if self.incoming is not None and getattr(event, "incoming", True) != self.incoming:
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

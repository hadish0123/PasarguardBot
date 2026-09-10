from __future__ import annotations
from dataclasses import dataclass

@dataclass
class _Button:
    kind: str
    text: str = ""
    data: bytes | str | None = None
    url: str | None = None
    request_contact: bool = False
    request_location: bool = False

    def to_dict(self):
        if self.kind == "inline":
            data = self.data.decode("utf-8") if isinstance(self.data, bytes) else self.data
            if self.url:
                return {"text": self.text, "url": self.url}
            return {"text": self.text, "callback_data": str(data or "")[:64]}
        result = {"text": self.text}
        if self.request_contact:
            result["request_contact"] = True
        if self.request_location:
            result["request_location"] = True
        return result

class Button:
    @staticmethod
    def inline(text, data=b""):
        return _Button("inline", text=text, data=data)
    @staticmethod
    def url(text, url):
        return _Button("inline", text=text, url=url)
    @staticmethod
    def text(text, resize=True, single_use=False):
        return _Button("text", text=text)
    @staticmethod
    def request_phone(text):
        return _Button("text", text=text, request_contact=True)
    @staticmethod
    def request_location(text):
        return _Button("text", text=text, request_location=True)
    @staticmethod
    def clear():
        return {"remove_keyboard": True}
    @staticmethod
    def force_reply():
        return {"force_reply": True}

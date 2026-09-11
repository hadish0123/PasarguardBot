from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.exceptions import ValidationError


@dataclass(slots=True)
class RegistrationDraft:
    owner_id: int
    brand: str | None = None
    bot_token: str | None = None
    bot_id: int | None = None
    panel_url: str | None = None
    panel_username: str | None = None
    panel_api_key: str | None = None


class RegistrationService:
    """Central representative registration business flow."""

    @staticmethod
    def validate_brand(value: str) -> str:
        value = value.strip()
        if not 2 <= len(value) <= 120:
            raise ValidationError("نام برند باید بین ۲ تا ۱۲۰ کاراکتر باشد.")
        return value

    @staticmethod
    def validate_bot_id(value: str, expected: int) -> int:
        if not value.isdigit() or int(value) != expected:
            raise ValidationError("شناسه ربات با Bot Token مطابقت ندارد.")
        return int(value)

    @staticmethod
    def normalize_panel_url(value: str) -> str:
        value = value.strip().rstrip("/")
        if value.endswith("/dashboard"):
            value = value[:-9].rstrip("/")
        if not value.startswith(("http://", "https://")):
            value = "https://" + value
        if " " in value:
            raise ValidationError("آدرس پنل معتبر نیست.")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError("آدرس پنل معتبر نیست.")
        return value.rstrip("/")

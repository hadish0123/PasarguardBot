from __future__ import annotations

import httpx

from app.core.exceptions import ValidationError


class TelegramBotVerifier:
    """Validate a representative bot token through Telegram's official Bot API."""

    async def get_me(self, token: str) -> dict:
        token = token.strip()
        if not token or ":" not in token:
            raise ValidationError("Bot Token معتبر نیست.")
        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(url)
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ValidationError("اعتبارسنجی Bot Token انجام نشد؛ دوباره تلاش کنید.") from exc
        if response.status_code != 200 or not payload.get("ok") or not payload.get("result"):
            raise ValidationError("Bot Token نادرست یا منقضی است.")
        return payload["result"]

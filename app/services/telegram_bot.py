from __future__ import annotations

import asyncio

import httpx

from app.core.exceptions import ValidationError


class TelegramBotVerifier:
    """Validate representative bot tokens through Telegram's official Bot API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None and not self._client.is_closed:
            return self._client
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(8.0, connect=4.0),
                    limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
                )
            return self._client

    async def get_me(self, token: str) -> dict:
        token = token.strip()
        if not token or ":" not in token:
            raise ValidationError("Bot Token معتبر نیست.")
        url = f"https://api.telegram.org/bot{token}/getMe"
        client = await self._get_client()
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await client.get(url)
                try:
                    payload = response.json()
                except ValueError as exc:
                    last_error = exc
                    payload = None
                if payload and payload.get("ok") and payload.get("result"):
                    return payload["result"]
                if response.status_code in {401, 404} or (payload and payload.get("error_code") in {401, 404}):
                    raise ValidationError("Bot Token نادرست یا منقضی است.")
                description = (payload or {}).get("description", "")
                last_error = RuntimeError(description or f"Telegram HTTP {response.status_code}")
            except ValidationError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                last_error = exc
            except httpx.HTTPError as exc:
                last_error = exc
            if attempt < 2:
                await asyncio.sleep(0.35 * (attempt + 1))
        raise ValidationError("ارتباط با Telegram برای بررسی Bot Token برقرار نشد؛ چند لحظه بعد دوباره تلاش کنید.") from last_error

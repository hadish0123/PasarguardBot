from __future__ import annotations

import asyncio

from telethon import TelegramClient

from app.core.config import settings
from app.db.session import initialize_database
from app.telegram.central import register_central_handlers
from app.telegram.central.admin import register_central_admin_handlers


async def run(stop_event: asyncio.Event | None = None) -> None:
    if not settings.telegram_api_id or not settings.telegram_api_hash or not settings.central_bot_token:
        raise RuntimeError("API_ID, API_HASH and BOT_TOKEN are required")
    await initialize_database()
    client = TelegramClient("central", settings.telegram_api_id, settings.telegram_api_hash)
    register_central_handlers(client)
    register_central_admin_handlers(client)
    await client.start(bot_token=settings.central_bot_token)
    if stop_event is None:
        await client.run_until_disconnected()
        return
    await stop_event.wait()
    await client.disconnect()

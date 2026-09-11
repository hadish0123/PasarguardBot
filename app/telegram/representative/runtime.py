from __future__ import annotations

from telethon import TelegramClient, events

from app.core.config import settings
from app.runtime.dispatcher import tenant_dispatch


class RepresentativeRuntime:
    """One isolated Telegram runtime per representative tenant."""

    def __init__(self, tenant_id: str, bot_token: str):
        self.tenant_id = tenant_id
        self.bot_token = bot_token
        self.client = TelegramClient(
            f"tenant-{tenant_id}", settings.telegram_api_id, settings.telegram_api_hash
        )
        self.is_running = False

    def register(self) -> None:
        self.client.add_event_handler(self._start, events.NewMessage(pattern=r"^/start$"))

    async def _start(self, event):
        async with tenant_dispatch(self.tenant_id):
            await event.respond(
                "🏪 **فروشگاه نمایندگی**\n\n"
                "به فروشگاه خوش آمدید.\n"
                "از این ربات می‌توانید سرویس خریداری کنید، سرویس‌های خود را ببینید و حساب کاربری را مدیریت کنید."
            )

    async def start(self) -> None:
        if self.is_running:
            return
        self.register()
        await self.client.start(bot_token=self.bot_token)
        self.is_running = True

    async def stop(self) -> None:
        if self.is_running:
            await self.client.disconnect()
        self.is_running = False

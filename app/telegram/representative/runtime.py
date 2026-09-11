from __future__ import annotations

from telethon import TelegramClient, events

from app.core.config import settings
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService


class RepresentativeRuntime:
    """One isolated Telegram runtime per representative tenant."""

    def __init__(self, tenant_id: str, bot_token: str):
        self.tenant_id = tenant_id
        self.bot_token = bot_token
        self.client = TelegramClient(f"tenant-{tenant_id}", settings.telegram_api_id, settings.telegram_api_hash)
        self.is_running = False
        self.dashboard = RepresentativeDashboardService()

    def register(self) -> None:
        self.client.add_event_handler(self._start, events.NewMessage(pattern=r"^/start$"))
        from app.telegram.representative.admin import register as register_admin
        from app.telegram.representative.plans import register as register_plans
        register_admin(self.client, self.tenant_id)
        register_plans(self.client, self.tenant_id)

    async def _start(self, event):
        async with tenant_dispatch(self.tenant_id):
            if await self.dashboard.is_owner(event.sender_id):
                from app.telegram.representative.admin import dashboard_text, ADMIN_MENU
                await event.respond(await dashboard_text(), buttons=ADMIN_MENU)
                return
            from app.telegram.representative.user import USER_MENU
            await event.respond("🏪 **فروشگاه**\n\nبه فروشگاه نمایندگی خوش آمدید. از گزینه‌های زیر شروع کنید.", buttons=USER_MENU)

    async def start(self) -> None:
        if self.is_running: return
        self.register()
        await self.client.start(bot_token=self.bot_token)
        self.is_running = True

    async def stop(self) -> None:
        if self.is_running: await self.client.disconnect()
        self.is_running = False

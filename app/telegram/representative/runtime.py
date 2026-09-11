from __future__ import annotations

from telethon import TelegramClient, events

from app.core.config import settings
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.representative_users import SERVICE as USER_SERVICE
from app.services.texts import SERVICE as TEXT_SERVICE


class RepresentativeRuntime:
    def __init__(self, tenant_id: str, bot_token: str):
        self.tenant_id = tenant_id
        self.bot_token = bot_token
        self.client = TelegramClient(f"tenant-{tenant_id}", settings.telegram_api_id, settings.telegram_api_hash)
        self.is_running = False
        self.dashboard = RepresentativeDashboardService()

    def register(self):
        self.client.add_event_handler(self._start, events.NewMessage(pattern=r"^/start$"))
        from app.telegram.representative.admin import register as a
        from app.telegram.representative.plans import register as p
        from app.telegram.representative.users import register as u
        from app.telegram.representative.orders import register as o
        from app.telegram.representative.discounts import register as d
        from app.telegram.representative.sales import register as s
        from app.telegram.representative.texts import register as t
        from app.telegram.representative.logs import register as l
        from app.telegram.representative.links import register as k
        from app.telegram.representative.settings import register as r
        from app.telegram.representative.panel import register as h
        from app.telegram.representative.user import register as c
        from app.telegram.representative.user_services import register as us
        from app.telegram.representative.wallet import register as w
        from app.telegram.representative.profile import register as pr
        a(self.client, self.tenant_id)
        p(self.client, self.tenant_id)
        u(self.client, self.tenant_id)
        o(self.client, self.tenant_id)
        d(self.client, self.tenant_id)
        s(self.client, self.tenant_id)
        t(self.client, self.tenant_id)
        l(self.client, self.tenant_id)
        k(self.client, self.tenant_id)
        r(self.client, self.tenant_id)
        h(self.client, self.tenant_id)
        c(self.client, self.tenant_id)
        us(self.client, self.tenant_id)
        w(self.client, self.tenant_id)
        pr(self.client, self.tenant_id)

    async def _start(self, event):
        async with tenant_dispatch(self.tenant_id):
            if await self.dashboard.is_owner(event.sender_id):
                from app.telegram.representative.admin import dashboard_text, ADMIN_MENU
                return await event.respond(await dashboard_text(), buttons=ADMIN_MENU)
            user = await USER_SERVICE.upsert_from_sender(await event.get_sender())
            if user.blocked:
                return await event.respond(await TEXT_SERVICE.get("blocked_user"))
            from app.telegram.representative.user import customer_menu
            await event.respond(await TEXT_SERVICE.get("welcome"), buttons=await customer_menu())

    async def start(self):
        if self.is_running:
            return
        self.register()
        await self.client.start(bot_token=self.bot_token)
        self.is_running = True

    async def stop(self):
        if self.is_running:
            await self.client.disconnect()
        self.is_running = False

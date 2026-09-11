from __future__ import annotations

from telethon import Button, events

from app.core.ids import REP_DISCOUNTS, REP_HOME, REP_LINKS, REP_LOGS, REP_ORDERS, REP_PANEL, REP_PLANS, REP_SALES, REP_SETTINGS, REP_TEXTS, REP_USERS
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService

SERVICE = RepresentativeDashboardService()
PREFIX = b"rep:"
ADMIN_MENU = [
    [Button.inline("📊 داشبورد", PREFIX + REP_HOME.encode())],
    [Button.inline("🗂 مدیریت پلن‌ها", PREFIX + REP_PLANS.encode()), Button.inline("👥 کاربران", PREFIX + REP_USERS.encode())],
    [Button.inline("🛒 فروش و سفارش‌ها", PREFIX + REP_ORDERS.encode())],
    [Button.inline("🎟 تخفیف‌ها", PREFIX + REP_DISCOUNTS.encode()), Button.inline("⚙️ تنظیمات فروش", PREFIX + REP_SALES.encode())],
    [Button.inline("🔌 اتصال پنل پاسارگارد", PREFIX + REP_PANEL.encode())],
    [Button.inline("📝 متن‌ها و دکمه‌ها", PREFIX + REP_TEXTS.encode())],
    [Button.inline("📋 لاگ‌ها", PREFIX + REP_LOGS.encode()), Button.inline("🔗 لینک‌ها", PREFIX + REP_LINKS.encode())],
    [Button.inline("⚙️ تنظیمات نماینده", PREFIX + REP_SETTINGS.encode())],
]


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            await admin_callback(event)

    client.add_event_handler(show_admin, events.NewMessage(pattern=r"^/admin$"))
    client.add_event_handler(callback, events.CallbackQuery(data=PREFIX))


async def _authorized(event):
    return bool(event.is_private and get_tenant() and await SERVICE.is_owner(event.sender_id))


async def dashboard_text():
    d = await SERVICE.snapshot()
    bot = f"@{d['bot_username']}" if d["bot_username"] else "در حال شناسایی"
    return f"📊 **داشبورد نماینده**\n\n🏷 برند: **{d['brand']}**\n🤖 ربات: **{bot}**\n🟢 وضعیت: **فعال**\n\nاز منوی زیر مدیریت فروشگاه و سرویس‌های نمایندگی را انجام دهید."


async def show_admin(event):
    if await _authorized(event):
        await event.respond(await dashboard_text(), buttons=ADMIN_MENU)


async def admin_callback(event):
    if not await _authorized(event):
        return await event.answer("دسترسی مدیریت ندارید.", alert=True)
    if event.data.startswith((
        b"rep:plans:", b"rep:users:", b"rep:orders:", b"rep:discounts:",
        b"rep:sales:", b"rep:texts:", b"rep:logs:", b"rep:links:",
        b"rep:settings:", b"rep:panel:",
    )):
        return
    action = event.data[len(PREFIX):].decode(errors="ignore")
    if action == REP_HOME:
        await event.edit(await dashboard_text(), buttons=ADMIN_MENU)
        return await event.answer()
    if action == REP_PLANS:
        from app.telegram.representative.plans import render
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    if action == REP_USERS:
        from app.telegram.representative.users import render
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    if action == REP_ORDERS:
        from app.telegram.representative.orders import render
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    if action == REP_DISCOUNTS:
        from app.telegram.representative.discounts import render
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    if action == REP_SALES:
        from app.telegram.representative.sales import render
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    if action == REP_PANEL:
        from app.telegram.representative.panel import render
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    if action == REP_TEXTS:
        from app.telegram.representative.texts import render
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    if action == REP_LOGS:
        from app.telegram.representative.logs import render
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    if action == REP_LINKS:
        from app.telegram.representative.links import render
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    if action == REP_SETTINGS:
        from app.telegram.representative.settings import render
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    await event.answer("گزینه نامعتبر است.", alert=True)

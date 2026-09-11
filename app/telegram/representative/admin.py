from __future__ import annotations

from telethon import Button, events

from app.core.ids import REP_HOME, REP_DISCOUNTS, REP_LINKS, REP_LOGS, REP_ORDERS, REP_PLANS, REP_SALES, REP_SETTINGS, REP_TEXTS, REP_USERS
from app.services.representative_dashboard import RepresentativeDashboardService
from app.runtime.context import get_tenant


SERVICE = RepresentativeDashboardService()
PREFIX = b"rep:"

ADMIN_MENU = [
    [Button.inline("📊 داشبورد", PREFIX + REP_HOME.encode())],
    [Button.inline("🗂 مدیریت پلن‌ها", PREFIX + REP_PLANS.encode()), Button.inline("👥 کاربران", PREFIX + REP_USERS.encode())],
    [Button.inline("🛒 فروش و سفارش‌ها", PREFIX + REP_ORDERS.encode())],
    [Button.inline("🎟 تخفیف‌ها", PREFIX + REP_DISCOUNTS.encode()), Button.inline("⚙️ تنظیمات فروش", PREFIX + REP_SALES.encode())],
    [Button.inline("📝 متن‌ها و دکمه‌ها", PREFIX + REP_TEXTS.encode())],
    [Button.inline("📋 لاگ‌ها", PREFIX + REP_LOGS.encode()), Button.inline("🔗 لینک‌ها", PREFIX + REP_LINKS.encode())],
    [Button.inline("⚙️ تنظیمات نماینده", PREFIX + REP_SETTINGS.encode())],
]


def register(client) -> None:
    client.add_event_handler(show_admin, events.NewMessage(pattern=r"^/admin$"))
    client.add_event_handler(admin_callback, events.CallbackQuery(data=PREFIX))


async def _authorized(event) -> bool:
    if not event.is_private or not get_tenant():
        return False
    return await SERVICE.is_owner(event.sender_id)


async def dashboard_text() -> str:
    data = await SERVICE.snapshot()
    bot = f"@{data['bot_username']}" if data["bot_username"] else "در حال شناسایی"
    return f"📊 **داشبورد نماینده**\n\n🏷 برند: **{data['brand']}**\n🤖 ربات: **{bot}**\n🟢 وضعیت: **فعال**\n\nاز منوی زیر مدیریت فروشگاه و سرویس‌های نمایندگی را انجام دهید."


async def show_admin(event) -> None:
    if not await _authorized(event):
        return
    await event.respond(await dashboard_text(), buttons=ADMIN_MENU)


async def admin_callback(event) -> None:
    if not await _authorized(event):
        await event.answer("دسترسی مدیریت ندارید.", alert=True)
        return
    if event.data.startswith(b"rep:plans:"):
        return
    action = event.data[len(PREFIX):].decode(errors="ignore")
    if action == REP_HOME:
        await event.edit(await dashboard_text(), buttons=ADMIN_MENU)
        await event.answer()
        return
    labels = {
        REP_PLANS: "🗂 مدیریت پلن‌ها",
        REP_USERS: "👥 کاربران",
        REP_ORDERS: "🛒 فروش و سفارش‌ها",
        REP_DISCOUNTS: "🎟 تخفیف‌ها",
        REP_SALES: "⚙️ تنظیمات فروش",
        REP_TEXTS: "📝 متن‌ها و دکمه‌ها",
        REP_LOGS: "📋 لاگ‌ها",
        REP_LINKS: "🔗 لینک‌ها",
        REP_SETTINGS: "⚙️ تنظیمات نماینده",
    }
    if action == REP_PLANS:
        from app.telegram.representative.plans import render
        text, buttons = await render()
        await event.edit(text, buttons=buttons)
        await event.answer()
        return
    if action in labels:
        await event.edit(f"{labels[action]}\n\nاین بخش در مرحله بعدی معماری نمایندگی به‌صورت کامل فعال می‌شود.", buttons=[[Button.inline("📊 داشبورد", PREFIX + REP_HOME.encode())]])
        await event.answer()
        return
    await event.answer("گزینه نامعتبر است.", alert=True)

from __future__ import annotations

from telethon import Button, events

from app.core.ids import USER_HOME, USER_SERVICES
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.user_services import SERVICE
from app.services.representative_users import SERVICE as USERS

PREFIX = b"user:services:"


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await allowed(event):
                return await event.answer("دسترسی به این بخش ندارید.", alert=True)
            await render_callback(event)
    client.add_event_handler(callback, events.CallbackQuery(data=PREFIX))


async def allowed(event):
    if not event.is_private or not get_tenant():
        return False
    user = await USERS.get_by_telegram_id(event.sender_id)
    return bool(user and not user.blocked)


async def render():
    return await _render_text(SERVICE.orders)


async def _render_text(loader):
    # The caller supplies the tenant-scoped order query; no cross-tenant data is exposed.
    return "📦 **سرویس‌های من**"


async def render_user(telegram_user_id: int):
    orders = await SERVICE.orders(telegram_user_id)
    if not orders:
        text = "📦 **سرویس‌های من**\n\nهنوز سفارشی برای شما ثبت نشده است."
    else:
        active = [o for o in orders if o.status == "fulfilled"]
        pending = [o for o in orders if o.status == "pending"]
        text = f"📦 **سرویس‌های من**\n\n🟢 فعال: **{len(active)}**\n⏳ در انتظار: **{len(pending)}**\n📋 مجموع سفارش‌ها: **{len(orders)}**\n\n"
        text += "\n".join(f"• #{o.id} — {o.plan_name} — {o.status}" for o in orders[:10])
    buttons = [[Button.inline("🔙 فروشگاه", b"user:" + USER_HOME.encode())]]
    return text, buttons


async def render_callback(event):
    action = event.data[len(PREFIX):].decode(errors="ignore")
    if action in ("", "list"):
        text, buttons = await render_user(event.sender_id)
        await event.edit(text, buttons=buttons)
        return await event.answer()
    if action.startswith("view:"):
        try:
            order_id = int(action.split(":", 1)[1])
        except ValueError:
            return await event.answer("شناسه سفارش نامعتبر است.", alert=True)
        order = await SERVICE.orders(event.sender_id)
        order = next((item for item in order if item.id == order_id), None)
        if order is None:
            return await event.answer("سفارش پیدا نشد.", alert=True)
        await event.edit(f"📦 **سفارش #{order.id}**\n\nپلن: **{order.plan_name}**\nحجم: **{order.volume_gb:g} GB**\nمدت: **{order.days} روز**\nمبلغ: **{order.amount:,.2f}**\nوضعیت: **{order.status}**", buttons=[[Button.inline("🔙 سرویس‌ها", PREFIX + b"list")]])
        return await event.answer()
    await event.answer("گزینه نامعتبر است.", alert=True)

from __future__ import annotations

from telethon import Button, events

from app.core.ids import USER_HOME
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


def _status(status: str) -> str:
    return {
        "pending": "⏳ در انتظار پرداخت",
        "paid": "💳 پرداخت‌شده",
        "fulfilled": "🟢 فعال",
        "cancelled": "❌ لغوشده",
    }.get(status, status)


async def render_user(telegram_user_id: int):
    orders = await SERVICE.orders(telegram_user_id)
    if not orders:
        text = "📦 **سرویس‌های من**\n\nهنوز سفارشی برای شما ثبت نشده است."
        buttons = [[Button.inline("🔙 فروشگاه", b"user:" + USER_HOME.encode())]]
        return text, buttons

    active = [o for o in orders if o.status == "fulfilled"]
    pending = [o for o in orders if o.status == "pending"]
    text = (
        "📦 **سرویس‌های من**\n\n"
        f"🟢 فعال: **{len(active)}**\n"
        f"⏳ در انتظار: **{len(pending)}**\n"
        f"📋 مجموع سفارش‌ها: **{len(orders)}**\n\n"
        "سفارش موردنظر را انتخاب کنید:"
    )
    buttons = [
        [Button.inline(f"#{o.id} • {o.plan_name} • {_status(o.status)}", PREFIX + f"view:{o.id}".encode())]
        for o in orders[:10]
    ]
    buttons.append([Button.inline("🔄 بروزرسانی", PREFIX + b"list")])
    buttons.append([Button.inline("🔙 فروشگاه", b"user:" + USER_HOME.encode())])
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

        orders = await SERVICE.orders(event.sender_id)
        order = next((item for item in orders if item.id == order_id), None)
        if order is None:
            return await event.answer("سفارش پیدا نشد.", alert=True)

        text = (
            f"📦 **سفارش #{order.id}**\n\n"
            f"📌 پلن: **{order.plan_name}**\n"
            f"💾 حجم: **{order.volume_gb:g} GB**\n"
            f"📅 مدت: **{order.days} روز**\n"
            f"💰 مبلغ: **{order.amount:,.2f}**\n"
            f"📊 وضعیت: **{_status(order.status)}**"
        )
        buttons = [
            [Button.inline("🔄 بروزرسانی", PREFIX + b"view:" + str(order.id).encode())],
            [Button.inline("🔙 سرویس‌های من", PREFIX + b"list")],
        ]
        await event.edit(text, buttons=buttons)
        return await event.answer()

    await event.answer("گزینه نامعتبر است.", alert=True)

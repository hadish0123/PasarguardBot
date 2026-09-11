from __future__ import annotations

from telethon import Button, events

from app.core.ids import REP_HOME, REP_SALES
from app.runtime.dispatcher import tenant_dispatch
from app.runtime.context import get_tenant
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.sales_settings import SERVICE

PREFIX = b"rep:sales:"


def register(client, tenant_id: str | None = None) -> None:
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await _authorized(event):
                await event.answer("دسترسی مدیریت ندارید.", alert=True)
                return
            await handle(event)
    client.add_event_handler(callback, events.CallbackQuery(data=PREFIX))
    client.add_event_handler(callback, events.CallbackQuery(data=b"rep:" + REP_SALES.encode()))


async def _authorized(event) -> bool:
    if not event.is_private or not get_tenant():
        return False
    return await RepresentativeDashboardService().is_owner(event.sender_id)


async def render():
    data = await SERVICE.snapshot()
    on = lambda value: "🟢 روشن" if value else "🔴 خاموش"
    text = (
        "⚙️ **تنظیمات فروش**\n\n"
        f"🛍 فروش: {on(data['sales_enabled'])}\n"
        f"💳 تأیید پرداخت توسط نماینده: {on(data['require_payment_confirmation'])}\n"
        f"📦 ایجاد سفارش در انتظار پرداخت: {on(data['allow_pending_orders'])}\n"
        f"💰 واحد قیمت: **{data['currency']}**\n"
        f"🆘 پشتیبانی: **{data['support_username'] or 'تنظیم نشده'}**"
    )
    buttons = [
        [Button.inline(f"🛍 فروش {on(data['sales_enabled'])}", PREFIX + b"sales")],
        [Button.inline(f"💳 تأیید پرداخت {on(data['require_payment_confirmation'])}", PREFIX + b"payment")],
        [Button.inline(f"📦 سفارش معلق {on(data['allow_pending_orders'])}", PREFIX + b"pending")],
        [Button.inline("💰 واحد قیمت", PREFIX + b"currency")],
        [Button.inline("🆘 پشتیبانی", PREFIX + b"support")],
        [Button.inline("📊 داشبورد", b"rep:" + REP_HOME.encode())],
    ]
    return text, buttons


async def handle(event):
    action = event.data[len(PREFIX):]
    if action == b"sales":
        current = await SERVICE.snapshot()
        await SERVICE.set("sales_enabled", not current["sales_enabled"])
    elif action == b"payment":
        current = await SERVICE.snapshot()
        await SERVICE.set("require_payment_confirmation", not current["require_payment_confirmation"])
    elif action == b"pending":
        current = await SERVICE.snapshot()
        await SERVICE.set("allow_pending_orders", not current["allow_pending_orders"])
    elif action == b"currency":
        await event.answer("برای تغییر واحد قیمت در نسخه بعدی ویزارد تنظیمات تکمیل می‌شود.", alert=True)
        return
    elif action == b"support":
        await event.answer("برای تغییر پشتیبانی در نسخه بعدی ویزارد تنظیمات تکمیل می‌شود.", alert=True)
        return
    else:
        await event.answer("گزینه نامعتبر است.", alert=True)
        return
    text, buttons = await render()
    await event.edit(text, buttons=buttons)
    await event.answer("ذخیره شد.")

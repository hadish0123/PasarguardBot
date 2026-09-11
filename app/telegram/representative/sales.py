from __future__ import annotations

from telethon import Button, events
from app.core.ids import REP_HOME, REP_SALES
from app.runtime.dispatcher import tenant_dispatch
from app.runtime.context import get_tenant
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.sales_settings import SERVICE

PREFIX = b"rep:sales:"
_INPUTS: dict[tuple[str, int], str] = {}


def register(client, tenant_id: str | None = None) -> None:
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await _authorized(event):
                return await event.answer("دسترسی مدیریت ندارید.", alert=True)
            await handle(event)

    async def message(event):
        async with tenant_dispatch(tenant_id):
            if not await _authorized(event):
                return
            key = (get_tenant(), event.sender_id)
            mode = _INPUTS.get(key)
            if not mode:
                return
            value = (event.raw_text or "").strip()
            if value.lower() == "/cancel" or value == "لغو":
                _INPUTS.pop(key, None)
                return await event.respond("❌ عملیات لغو شد.")
            try:
                if mode == "currency":
                    if not 1 <= len(value) <= 30:
                        raise ValueError("واحد قیمت باید بین 1 تا 30 کاراکتر باشد.")
                    await SERVICE.set("currency", value)
                else:
                    username = value.lstrip("@").strip()
                    if username and (len(username) > 64 or not username.replace("_", "").isalnum()):
                        raise ValueError("نام کاربری تلگرام معتبر نیست.")
                    await SERVICE.set("support_username", username)
                _INPUTS.pop(key, None)
                text, buttons = await render()
                await event.respond("✅ تنظیمات ذخیره شد.", buttons=buttons)
                await event.respond(text, buttons=buttons)
            except ValueError as exc:
                await event.respond(f"❌ {exc}\n\nمقدار دیگری ارسال کنید یا `/cancel` بزنید.")

    client.add_event_handler(
        callback,
        events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))),
    )
    client.add_event_handler(callback, events.CallbackQuery(data=b"rep:" + REP_SALES.encode()))
    client.add_event_handler(message, events.NewMessage(incoming=True))


async def _authorized(event) -> bool:
    return bool(
        event.is_private
        and get_tenant()
        and await RepresentativeDashboardService().is_owner(event.sender_id)
    )


async def render():
    data = await SERVICE.snapshot()
    on = lambda v: "🟢 روشن" if v else "🔴 خاموش"
    support = f"@{data['support_username']}" if data["support_username"] else "تنظیم نشده"
    text = (
        "⚙️ **تنظیمات فروش**\n\n"
        f"🛍 فروش: {on(data['sales_enabled'])}\n"
        f"💳 تأیید پرداخت: {on(data['require_payment_confirmation'])}\n"
        f"📦 سفارش معلق: {on(data['allow_pending_orders'])}\n"
        f"💰 واحد قیمت: **{data['currency']}**\n"
        f"🆘 پشتیبانی: **{support}**\n\n"
        "تغییرات این صفحه روی Checkout و رفتار فروش اعمال می‌شوند."
    )
    buttons = [
        [Button.inline(f"🛍 فروش {on(data['sales_enabled'])}", PREFIX + b"sales")],
        [Button.inline(f"💳 تأیید پرداخت {on(data['require_payment_confirmation'])}", PREFIX + b"payment")],
        [Button.inline(f"📦 سفارش معلق {on(data['allow_pending_orders'])}", PREFIX + b"pending")],
        [Button.inline("💰 تغییر واحد قیمت", PREFIX + b"currency")],
        [Button.inline("🆘 تغییر پشتیبانی", PREFIX + b"support")],
        [Button.inline("📊 داشبورد", b"rep:" + REP_HOME.encode())],
    ]
    return text, buttons


async def handle(event):
    action = event.data[len(PREFIX):]
    key = (get_tenant(), event.sender_id)
    if action in {b"sales", b"payment", b"pending"}:
        current = await SERVICE.snapshot()
        mapping = {
            b"sales": "sales_enabled",
            b"payment": "require_payment_confirmation",
            b"pending": "allow_pending_orders",
        }
        field = mapping[action]
        await SERVICE.set(field, not current[field])
    elif action == b"currency":
        _INPUTS[key] = "currency"
        return await event.edit(
            "💰 **واحد قیمت جدید**\n\nمثلاً `تومان` یا `USD` را ارسال کنید.",
            buttons=[[Button.inline("❌ لغو", PREFIX + b"cancel")]],
        )
    elif action == b"support":
        _INPUTS[key] = "support"
        return await event.edit(
            "🆘 **پشتیبانی**\n\nنام کاربری پشتیبانی را ارسال کنید؛ مثلاً `support_team`.\nبرای حذف، خالی یا `/cancel` بفرستید.",
            buttons=[[Button.inline("❌ لغو", PREFIX + b"cancel")]],
        )
    elif action == b"cancel":
        _INPUTS.pop(key, None)
    else:
        return await event.answer("گزینه نامعتبر است.", alert=True)
    text, buttons = await render()
    await event.edit(text, buttons=buttons)
    await event.answer("ذخیره شد.")

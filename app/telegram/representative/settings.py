from __future__ import annotations

from telethon import Button, events

from app.core.ids import REP_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.representative_settings import SERVICE

PREFIX = b"rep:settings:"
INPUTS: dict[tuple[str, int], str] = {}


def register(client, tenant_id=None):
    async def cb(event):
        async with tenant_dispatch(tenant_id):
            if not await _auth(event):
                return await event.answer("دسترسی مدیریت ندارید.", alert=True)
            await handle(event)

    async def msg(event):
        async with tenant_dispatch(tenant_id):
            if not await _auth(event):
                return
            key = (get_tenant(), event.sender_id)
            field = INPUTS.get(key)
            if not field:
                return
            value = event.raw_text.strip()
            if value in {"/cancel", "لغو"}:
                INPUTS.pop(key, None)
                return await event.respond("❌ عملیات لغو شد.", buttons=(await render())[1])
            try:
                await SERVICE.set(field, value)
            except ValueError as exc:
                return await event.respond(f"❌ {exc}\n\nمقدار را اصلاح کنید یا `/cancel` بزنید.")
            INPUTS.pop(key, None)
            text, buttons = await render()
            await event.respond("✅ تنظیمات ذخیره شد.", buttons=buttons)

    client.add_event_handler(
        cb,
        events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))),
    )
    client.add_event_handler(msg, events.NewMessage(incoming=True))


async def _auth(event):
    return bool(
        event.is_private
        and get_tenant()
        and await RepresentativeDashboardService().is_owner(event.sender_id)
    )


async def render():
    s = await SERVICE.snapshot()
    brand = s["brand"] or "پیش‌فرض ثبت‌نام"
    support = ("@" + s["support_username"]) if s["support_username"] else "تنظیم نشده"
    card = s["payment_card_number"] or "تنظیم نشده"
    holder = s["payment_card_holder"] or "تنظیم نشده"
    return (
        "⚙️ **تنظیمات نماینده**\n\n"
        f"🏷 برند: **{brand}**\n"
        f"🆘 پشتیبانی: **{support}**\n"
        f"🌍 منطقه زمانی: **{s['timezone']}**\n\n"
        "💳 **اطلاعات پرداخت فروشگاه**\n"
        f"💳 شماره کارت: **{card}**\n"
        f"👤 به نام: **{holder}**\n\n"
        "این تنظیمات فقط برای همین نماینده ذخیره می‌شود.",
        [
            [Button.inline("🏷 ویرایش برند", PREFIX + b"edit:brand")],
            [Button.inline("🆘 پشتیبانی", PREFIX + b"edit:support_username")],
            [Button.inline("🌍 منطقه زمانی", PREFIX + b"edit:timezone")],
            [Button.inline("💳 شماره کارت", PREFIX + b"edit:payment_card_number")],
            [Button.inline("👤 نام صاحب کارت", PREFIX + b"edit:payment_card_holder")],
            [Button.inline("🔄 تازه‌سازی", PREFIX + b"list")],
            [Button.inline("📊 داشبورد", b"rep:" + REP_HOME.encode())],
        ],
    )


async def handle(event):
    action = (event.data[len(PREFIX):] if event.data.startswith(PREFIX) else b"").decode(errors="ignore")
    key = (get_tenant(), event.sender_id)
    if action.startswith("edit:"):
        field = action[5:]
        prompts = {
            "brand": "🏷 نام برند جدید را ارسال کنید:",
            "support_username": "🆘 یوزرنیم پشتیبانی را ارسال کنید (مثال: support):",
            "timezone": "🌍 منطقه زمانی را ارسال کنید (مثال: Asia/Tehran):",
            "payment_card_number": "💳 شماره کارت ۱۶ رقمی را ارسال کنید:",
            "payment_card_holder": "👤 نام و نام خانوادگی صاحب کارت را ارسال کنید:",
        }
        if field not in prompts:
            return await event.answer("تنظیم نامعتبر است.", alert=True)
        INPUTS[key] = field
        return await event.edit(
            prompts[field] + "\n\nبرای لغو `/cancel`",
            buttons=[[Button.inline("❌ لغو", PREFIX + b"list")]],
        )
    if action == "list":
        text, buttons = await render()
        return await event.edit(text, buttons=buttons)
    return await event.answer("گزینه نامعتبر است.", alert=True)

from __future__ import annotations

from telethon import Button, events

from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.orders import SERVICE as ORDER_SERVICE
from app.services.plans import PlanService
from app.services.representative_users import SERVICE as USER_SERVICE

USER_PREFIX = b"user:"

USER_MENU = [
    [Button.inline("🛒 خرید سرویس", USER_PREFIX + b"buy")],
    [Button.inline("📦 سرویس‌های من", USER_PREFIX + b"services"), Button.inline("💳 کیف پول", USER_PREFIX + b"wallet")],
    [Button.inline("👤 پروفایل", USER_PREFIX + b"profile"), Button.inline("🎁 دعوت دوستان", USER_PREFIX + b"referral")],
    [Button.inline("🎟 کد تخفیف", USER_PREFIX + b"discount"), Button.inline("🎁 سرویس آزمایشی", USER_PREFIX + b"trial")],
    [Button.inline("🆘 پشتیبانی", USER_PREFIX + b"support")],
]


def register(client, tenant_id: str | None = None) -> None:
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            await callback_handler(event)
    client.add_event_handler(callback, events.CallbackQuery(data=USER_PREFIX))


async def _allowed(event) -> bool:
    if not event.is_private or not get_tenant():
        return False
    user = await USER_SERVICE.get_by_telegram(event.sender_id)
    return bool(user and not user.blocked)


async def show_home(event) -> None:
    await event.respond("🏪 **فروشگاه**\n\nیکی از گزینه‌های زیر را انتخاب کنید.", buttons=USER_MENU)


async def _buy(event) -> None:
    plans = [p for p in await PlanService().list() if p.enabled]
    if not plans:
        await event.edit("🛒 **خرید سرویس**\n\nدر حال حاضر پلن فعالی برای فروش وجود ندارد.", buttons=[[Button.inline("🔙 فروشگاه", USER_PREFIX + b"home")]])
        return
    rows = []
    for plan in plans:
        rows.append([Button.inline(f"📦 {plan.name} | {plan.volume_gb:g}GB / {plan.days}روز | {plan.price:g}", USER_PREFIX + f"order:{plan.id}".encode())])
    rows.append([Button.inline("🔙 فروشگاه", USER_PREFIX + b"home")])
    await event.edit("🛒 **انتخاب سرویس**\n\nپلن موردنظر را انتخاب کنید:", buttons=rows)


async def callback_handler(event) -> None:
    if not await _allowed(event):
        await event.answer("دسترسی به فروشگاه ندارید.", alert=True)
        return
    action = event.data[len(USER_PREFIX):].decode(errors="ignore")
    if action == "home":
        await event.edit("🏪 **فروشگاه**\n\nیکی از گزینه‌های زیر را انتخاب کنید.", buttons=USER_MENU); await event.answer(); return
    if action == "buy":
        await _buy(event); await event.answer(); return
    if action.startswith("order:"):
        try:
            order = await ORDER_SERVICE.create(event.sender_id, int(action.split(":", 1)[1]))
        except LookupError:
            await event.answer("این پلن دیگر قابل خرید نیست.", alert=True); return
        await event.edit(f"✅ **سفارش #{order.id} ثبت شد**\n\n📦 {order.plan_name}\n💰 مبلغ: **{order.amount:,.2f}**\n📌 وضعیت: **در انتظار پرداخت**\n\nسفارش شما برای نماینده ارسال شد.", buttons=[[Button.inline("🛒 خرید دوباره", USER_PREFIX + b"buy")], [Button.inline("🏪 فروشگاه", USER_PREFIX + b"home")]])
        await event.answer("سفارش ثبت شد.")
        return
    await event.answer("این بخش در صفحه‌های بعدی فعال می‌شود.", alert=True)

from __future__ import annotations
from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.orders import SERVICE as ORDER_SERVICE
from app.services.plans import PlanService
from app.services.representative_users import SERVICE as USER_SERVICE
from app.services.texts import SERVICE as TEXT_SERVICE

USER_PREFIX = b"user:"


async def customer_menu():
    v = await TEXT_SERVICE.all()
    return [
        [Button.inline(v["buy_button"], USER_PREFIX + b"buy")],
        [Button.inline(v["services_button"], USER_PREFIX + b"services"), Button.inline(v["wallet_button"], USER_PREFIX + b"wallet")],
        [Button.inline(v["profile_button"], USER_PREFIX + b"profile"), Button.inline(v["referral_button"], USER_PREFIX + b"referral")],
        [Button.inline(v["discount_button"], USER_PREFIX + b"discount"), Button.inline(v["trial_button"], USER_PREFIX + b"trial")],
        [Button.inline(v["support_button"], USER_PREFIX + b"support")],
    ]


def register(client, tenant_id=None):
    async def callback(event):
        # USER_PREFIX is a namespace, not a complete callback value.
        # The compatibility layer's exact data filter cannot match user:buy/order:123.
        raw = event.data
        try:
            data = bytes(raw or b"")
        except (TypeError, ValueError):
            data = b""
        if not data.startswith(USER_PREFIX):
            return
        async with tenant_dispatch(tenant_id):
            await callback_handler(event)

    client.add_event_handler(callback, events.CallbackQuery())


async def _allowed(event):
    if not event.is_private or not get_tenant():
        return False
    user = await USER_SERVICE.get_by_telegram_id(event.sender_id)
    return bool(user and not user.blocked)


async def show_home(event):
    await event.respond(
        await TEXT_SERVICE.get("shop_title") + "\n\n" + await TEXT_SERVICE.get("shop_hint"),
        buttons=await customer_menu(),
    )


async def _buy(event):
    plans = [p for p in await PlanService().list() if p.enabled]
    if not plans:
        return await event.edit(
            await TEXT_SERVICE.get("buy_title") + "\n\n" + await TEXT_SERVICE.get("plans_empty"),
            buttons=[[Button.inline("🔙 فروشگاه", USER_PREFIX + b"home")]],
        )
    rows = [
        [Button.inline(f"📦 {p.name} | {p.volume_gb:g}GB / {p.days}روز | {p.price:g}", USER_PREFIX + f"order:{p.id}".encode())]
        for p in plans
    ]
    rows.append([Button.inline("🔙 فروشگاه", USER_PREFIX + b"home")])
    await event.edit(await TEXT_SERVICE.get("buy_title") + "\n\n" + await TEXT_SERVICE.get("buy_hint"), buttons=rows)


async def callback_handler(event):
    if not await _allowed(event):
        return await event.answer("دسترسی به فروشگاه ندارید.", alert=True)

    raw = event.data
    try:
        data = bytes(raw or b"")
    except (TypeError, ValueError):
        data = b""
    if not data.startswith(USER_PREFIX):
        return

    action = data[len(USER_PREFIX):].decode(errors="ignore")

    # Only handle the base user namespace actions here. Specialized modules
    # own referral/trial/support callbacks and will receive them independently.
    if action == "home":
        await event.answer()
        return await event.edit(
            await TEXT_SERVICE.get("shop_title") + "\n\n" + await TEXT_SERVICE.get("shop_hint"),
            buttons=await customer_menu(),
        )

    if action == "buy":
        await event.answer()
        return await _buy(event)

    if action == "services":
        await event.answer()
        from app.telegram.representative.user_services import render_user
        text, buttons = await render_user(event.sender_id)
        return await event.edit(text, buttons=buttons)

    if action == "wallet":
        await event.answer()
        from app.telegram.representative.wallet import render_wallet
        text, buttons = await render_wallet(event.sender_id)
        return await event.edit(text, buttons=buttons)

    if action == "profile":
        await event.answer()
        from app.telegram.representative.profile import render_profile
        text, buttons = await render_profile(event.sender_id)
        return await event.edit(text, buttons=buttons)

    if action == "discount":
        await event.answer()
        from app.telegram.representative.discount_user import render
        return await render(event)

    if action.startswith("order:"):
        try:
            plan_id = int(action.split(":", 1)[1])
        except (ValueError, IndexError):
            return await event.answer("شناسه پلن نامعتبر است.", alert=True)

        # Acknowledge immediately so Telegram never shows a slow callback spinner
        # while the database/order operation is running.
        await event.answer("⏳ در حال ثبت سفارش...")
        try:
            order = await ORDER_SERVICE.create(event.sender_id, plan_id)
        except LookupError:
            return await event.edit(
                "❌ این پلن دیگر قابل خرید نیست.",
                buttons=[[Button.inline("🔙 بازگشت به خرید", USER_PREFIX + b"buy")]],
            )

        return await event.edit(
            f"✅ **سفارش #{order.id} ثبت شد**\n\n"
            f"📦 {order.plan_name}\n"
            f"💰 مبلغ: **{order.amount:,.2f}**\n"
            f"📌 وضعیت: **در انتظار پرداخت**",
            buttons=[
                [Button.inline("🛒 خرید دوباره", USER_PREFIX + b"buy")],
                [Button.inline("📦 سرویس‌های من", USER_PREFIX + b"services")],
                [Button.inline("🏪 فروشگاه", USER_PREFIX + b"home")],
            ],
        )

    # Let specialized user modules (referral/trial/support) handle their
    # own callbacks. Do not emit a false "invalid option" alert here.
    return

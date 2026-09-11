from __future__ import annotations

from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.plans import PlanService
from app.services.representative_users import SERVICE as USER_SERVICE
from app.services.texts import SERVICE as TEXT_SERVICE

USER_PREFIX = b"user:"


async def customer_menu(values: dict | None = None):
    from app.telegram.representative.navigation import customer_menu as _menu
    return await _menu(values)


def register(client, tenant_id=None):
    async def callback(event):
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
    values = await TEXT_SERVICE.all()
    await event.respond(
        values["shop_title"] + "\n\n" + values["shop_hint"],
        buttons=await customer_menu(values),
    )


async def _buy(event):
    plans = [p for p in await PlanService().list() if p.enabled]
    values = await TEXT_SERVICE.all()
    if not plans:
        return await event.edit(
            values["buy_title"] + "\n\n" + values["plans_empty"],
            buttons=[[Button.inline("🔙 فروشگاه", USER_PREFIX + b"home")]],
        )
    rows = [
        [Button.inline(f"📦 {p.name} | {p.volume_gb:g}GB / {p.days}روز | {p.price:g}", USER_PREFIX + f"order:{p.id}".encode())]
        for p in plans
    ]
    rows.append([Button.inline("🔙 فروشگاه", USER_PREFIX + b"home")])
    return await event.edit(values["buy_title"] + "\n\n" + values["buy_hint"], buttons=rows)


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

    if action == "home":
        await event.answer()
        values = await TEXT_SERVICE.all()
        return await event.edit(
            values["shop_title"] + "\n\n" + values["shop_hint"],
            buttons=await customer_menu(values),
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
        # The plan button must enter the real checkout flow. The previous
        # implementation created an order directly here and could race with
        # the dedicated checkout callback router, producing an invalid-option
        # response instead of the confirmation/payment screen.
        await event.answer()
        from app.telegram.representative.checkout import callback as checkout_callback
        return await checkout_callback(event, get_tenant())

    # referral/trial/support have their own namespaced handlers. They are
    # intentionally not rejected here so their specialized routers can run.
    return

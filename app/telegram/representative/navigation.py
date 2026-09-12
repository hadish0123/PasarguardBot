from __future__ import annotations

from telethon import Button, events

from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.plans import PlanService
from app.services.representative_users import SERVICE as USER_SERVICE
from app.services.texts import SERVICE as TEXT_SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService

HOME = b"user:home"
BUY = b"user:buy"
ADMIN = b"rep:home"
ORDER = b"user:order:"
PROFILE = b"user:profile:show"

DASHBOARD = RepresentativeDashboardService()


async def register_handler(event, tenant_id):
    async with tenant_dispatch(tenant_id):
        if not event.is_private or not get_tenant():
            return
        user = await USER_SERVICE.get_by_telegram_id(event.sender_id)
        if not user or user.blocked:
            return await event.answer("دسترسی ندارید.", alert=True)
        data = bytes(event.data or b"")
        await event.answer()
        if data == HOME:
            values = await TEXT_SERVICE.all()
            return await event.edit(
                values["shop_title"] + "\n\n" + values["shop_hint"],
                buttons=await customer_menu(values, await DASHBOARD.is_owner(event.sender_id)),
            )
        if data == ADMIN:
            if not await DASHBOARD.is_owner(event.sender_id):
                return await event.answer("دسترسی مدیریت ندارید.", alert=True)
            from app.telegram.representative.admin import dashboard_text, ADMIN_MENU
            return await event.edit(await dashboard_text(), buttons=ADMIN_MENU)
        if data == BUY:
            plans = [p for p in await PlanService().list() if p.enabled]
            if not plans:
                values = await TEXT_SERVICE.all()
                return await event.edit(
                    values["buy_title"] + "\n\n" + values["plans_empty"],
                    buttons=[[Button.inline("🔙 فروشگاه", HOME)]],
                )
            rows = [
                [Button.inline(f"📦 {p.name} | {p.volume_gb:g}GB / {p.days}روز | {p.price:g}", ORDER + str(p.id).encode())]
                for p in plans
            ]
            rows.append([Button.inline("🔙 فروشگاه", HOME)])
            values = await TEXT_SERVICE.all()
            return await event.edit(
                values["buy_title"] + "\n\n" + values["buy_hint"],
                buttons=rows,
            )


async def customer_menu(values: dict | None = None, is_owner: bool = False):
    values = values or await TEXT_SERVICE.all()
    rows = [
        [Button.inline(values["buy_button"], BUY)],
        [Button.inline(values["services_button"], b"user:services"), Button.inline(values["wallet_button"], b"user:wallet")],
        [Button.inline(values["profile_button"], PROFILE), Button.inline(values["referral_button"], b"user:referral")],
        [Button.inline(values["discount_button"], b"user:discount"), Button.inline(values["trial_button"], b"user:trial")],
        [Button.inline(values["support_button"], b"user:support")],
    ]
    if is_owner:
        rows.append([Button.inline("🛠 پنل مدیریت نمایندگی", ADMIN)])
    return rows


def register(client, tenant_id):
    client.add_event_handler(
        lambda event: register_handler(event, tenant_id),
        events.CallbackQuery(func=lambda e: bool(e.data and e.data in (HOME, BUY, ADMIN))),
    )

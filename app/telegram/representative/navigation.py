from __future__ import annotations

import re

from telethon import Button, events

from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.config_names import clear_pending, set_pending
from app.services.plans import PlanService
from app.services.representative_users import SERVICE as USER_SERVICE
from app.services.texts import SERVICE as TEXT_SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService

HOME = b"user:home"
BUY = b"user:buy"
ADMIN = b"rep:home"
ORDER = b"user:order:"
CONFIG_NAME = b"user:config-name:"
PROFILE = b"user:profile:show"

DASHBOARD = RepresentativeDashboardService()
_PENDING_PLAN: dict[tuple[str, int], int] = {}
_CONFIG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$")


def _volume_label(volume_gb) -> str:
    value = float(volume_gb or 0)
    return f"{value:g}GB"


def _price_label(price) -> str:
    return f"{round(float(price or 0)):,.0f} تومان"


def _plan_button_label(plan) -> str:
    # Keep each segment visually isolated in Telegram RTL rendering.
    # Visible order: 📦 Plan Name | 10GB | 30DAYS
    name = str(plan.name or "").strip()
    volume = _volume_label(plan.volume_gb)
    days = f"{int(plan.days)}DAYS"
    return f"\u202A📦 \u202B{name}\u202C | {volume} | {days}\u202C"


async def _ask_config_name(event, plan_id: int):
    key = (str(get_tenant()), int(event.sender_id))
    _PENDING_PLAN[key] = int(plan_id)
    return await event.edit(
        "📝 **نام کانفیگ را خودتان انتخاب کنید**\n\n"
        "نامی که وارد می‌کنید دقیقاً به‌عنوان نام سرویس در پاسارگاد ثبت می‌شود.\n\n"
        "مثال: `MyVPN-01`\n\n"
        "فقط حروف انگلیسی، عدد، `-`، `_` و `.` مجاز است.\n"
        "حداقل ۳ و حداکثر ۶۴ کاراکتر.\n\n"
        "نام کانفیگ را همینجا ارسال کنید:",
        buttons=[[Button.inline("❌ لغو", HOME)]],
    )


async def _config_name_input(event, tenant_id):
    async with tenant_dispatch(tenant_id):
        if not event.is_private or not get_tenant():
            return
        user = await USER_SERVICE.get_by_telegram_id(event.sender_id)
        if not user or user.blocked:
            return
        key = (str(tenant_id), int(event.sender_id))
        plan_id = _PENDING_PLAN.get(key)
        if plan_id is None:
            return
        text = (event.raw_text or "").strip()
        if text.lower() in {"/cancel", "لغو"}:
            _PENDING_PLAN.pop(key, None)
            clear_pending(tenant_id, event.sender_id)
            return await event.respond("❌ انتخاب نام کانفیگ لغو شد.", buttons=[[Button.inline("🏪 فروشگاه", HOME)]])
        if not _CONFIG_RE.fullmatch(text):
            return await event.respond(
                "❌ نام کانفیگ نامعتبر است.\n\n"
                "فقط حروف انگلیسی، عدد، `-`، `_` و `.` مجاز است؛ "
                "۳ تا ۶۴ کاراکتر.\n\nمثال: `MyVPN-01`"
            )

        plan = next((p for p in await PlanService().list() if p.id == plan_id and p.enabled), None)
        if plan is None:
            _PENDING_PLAN.pop(key, None)
            clear_pending(tenant_id, event.sender_id)
            return await event.respond("❌ این پلن دیگر فعال نیست.", buttons=[[Button.inline("🏪 فروشگاه", HOME)]])

        set_pending(tenant_id, event.sender_id, text)
        _PENDING_PLAN.pop(key, None)

        # Seed the existing checkout state, then show its normal payment flow.
        # This keeps discounts/wallet/card payment behavior unchanged.
        from app.telegram.representative import checkout
        checkout.STATE[checkout.key(tenant_id, event.sender_id)] = {"plan_id": int(plan.id)}
        subtotal = round(float(plan.price))
        detail = checkout._plan_detail(plan, subtotal, 0, subtotal, None)
        return await event.respond(
            f"✅ **نام کانفیگ:** `{text}`\n\n{detail}",
            buttons=[
                [Button.inline("💳 ادامه و دریافت شماره کارت", ORDER + b"pay")],
                [Button.inline("🎟 کد تخفیف", ORDER + b"discount"), Button.inline("🗑 حذف تخفیف", ORDER + b"clear")],
                [Button.inline("🔙 پلن‌ها", BUY), Button.inline("❌ لغو", HOME)],
            ],
        )


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
            _PENDING_PLAN.pop((str(tenant_id), int(event.sender_id)), None)
            clear_pending(tenant_id, event.sender_id)
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
                [Button.inline(_plan_button_label(p), CONFIG_NAME + str(p.id).encode())]
                for p in plans
            ]
            rows.append([Button.inline("🔙 فروشگاه", HOME)])
            values = await TEXT_SERVICE.all()
            return await event.edit(
                values["buy_title"] + "\n\n" + values["buy_hint"] + "\n\n" + "Plan: Volume • Duration",
                buttons=rows,
            )
        if data.startswith(CONFIG_NAME):
            raw_id = data[len(CONFIG_NAME):].decode(errors="ignore")
            if not raw_id.isdigit():
                return await event.answer("پلن نامعتبر است.", alert=True)
            return await _ask_config_name(event, int(raw_id))


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
        events.CallbackQuery(
            func=lambda e: bool(
                e.data and (e.data in (HOME, BUY, ADMIN) or bytes(e.data).startswith(CONFIG_NAME))
            )
        ),
    )
    client.add_event_handler(
        lambda event: _config_name_input(event, tenant_id),
        events.NewMessage(incoming=True),
    )

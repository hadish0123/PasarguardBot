"""Representative-only admin menu and tenant-safe management routing."""

from __future__ import annotations

from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.runtime.context import get_current_tenant, is_representative_runtime, is_runtime_admin
from app.services.panels.settings import (
    feature_settings,
    panel_custom_buy_enabled,
    panel_reseller_sale_flag,
    panel_shop_sale_flag,
    toggle_custom_buy_enabled,
    toggle_panel_sales_setting,
)
from app.telegram.admin.discounts.messages import message_handler_discount_admin
from app.telegram.admin.logs.messages import message_handler_log_admin
from app.telegram.admin.manage_user.messages import msg_manage_user_admin
from app.telegram.admin.panels.callbacks import panel_admin_callback_handler
from app.telegram.admin.panels.service import build_panel_summary_block, display_panels
from app.telegram.keyboards.customization import create_keyboard_buttons_admin_buttons
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.url_presets import format_admin_links_message, get_bot_username
from app.telegram.state import get_step, set_step

MODULE_NAME = "admin.representative_panel"
MODULE_ENABLED = True
MODULE_ORDER = 50

REP_MENU = {
    "🗂 پنل نماینده",
    "🗞 مدیریت پلن‌ها",
    "📊 وضعیت پنل",
    "⚙️ تنظیمات فروش",
    "🎟 کدهای تخفیف",
    "👥 کاربران",
    "📝 متن‌ها و دکمه‌ها",
    "📝 مدیریت لاگ‌ها",
    "🔗 لینک های آماده",
}


def _rep_admin(event) -> bool:
    return bool(is_representative_runtime() and is_runtime_admin(event.sender_id) and event.is_private)


async def _tenant_panel():
    tenant = get_current_tenant()
    if not tenant:
        return None
    return await PanelsManager().get_panel_by_code(tenant.registration_id)


async def _show_plan_menu(event):
    await event.respond(
        "🗞 **مدیریت پلن‌ها**\n\nپلن‌ها فقط برای پنل نماینده فعلی مدیریت می‌شوند.\nپنل جدید از این ربات قابل ثبت نیست.",
        buttons=[
            [Button.inline("➕ ساخت پلن جدید", data="PlanAddSelectPanel")],
            [Button.inline("📋 مدیریت پلن‌ها", data="PlanManageSelectPanel")],
            [Button.inline("🔙 بازگشت به پنل", data="back_to_admin_panel")],
        ],
        parse_mode="md",
    )


async def _show_sales_menu(event):
    panel = await _tenant_panel()
    if not panel:
        await event.respond("❌ پنل نماینده پیدا نشد.", buttons=[[Button.inline("🔙 بازگشت", data="back_to_admin_panel")]])
        return
    await event.respond(
        "⚙️ **تنظیمات فروش**\n\n"
        f"🏷 پنل: `{panel.name}`\n"
        f"🛒 فروش سرویس: {'فعال ✅' if panel_shop_sale_flag(panel) else 'غیرفعال ❌'}\n"
        f"🏢 فروش نمایندگی: {'فعال ✅' if panel_reseller_sale_flag(panel) else 'غیرفعال ❌'}\n"
        f"🧩 خرید سفارشی: {'آماده و فعال ✅' if panel_custom_buy_enabled(panel) else 'غیرفعال ❌'}\n\n"
        "هر تغییر مستقیماً روی همین پنل ذخیره می‌شود.",
        buttons=[
            [Button.inline("🛒 تغییر فروش سرویس", data="rep_sales_toggle:shop")],
            [Button.inline("🏢 تغییر فروش نمایندگی", data="rep_sales_toggle:reseller")],
            [Button.inline("🧩 تغییر خرید سفارشی", data="rep_sales_toggle:custom")],
            [Button.inline("🔙 بازگشت", data="back_to_admin_panel")],
        ],
        parse_mode="md",
    )


async def _rep_menu_handler(event: Message):
    if not _rep_admin(event):
        return
    msg = (event.message.text or "").strip()
    if msg not in REP_MENU:
        return

    if msg == "🗂 پنل نماینده":
        await display_panels(event.sender_id, current_page=1)
    elif msg == "📊 وضعیت پنل":
        panel = await _tenant_panel()
        if not panel:
            await event.respond("❌ پنل نماینده پیدا نشد.")
            return
        await event.respond(
            f"📊 **وضعیت پنل نماینده**\n\n<blockquote>{build_panel_summary_block(panel)}</blockquote>",
            parse_mode="html",
            buttons=[
                [Button.inline("⚙️ تنظیمات فروش", data="rep_sales_menu")],
                [Button.inline("📝 دکمه‌های کاربر", data="rep_keyboard_page:1")],
                [Button.inline("🔙 بازگشت", data="back_to_admin_panel")],
            ],
        )
    elif msg == "🗞 مدیریت پلن‌ها":
        await _show_plan_menu(event)
    elif msg == "⚙️ تنظیمات فروش":
        await _show_sales_menu(event)
    elif msg == "🎟 کدهای تخفیف":
        await event.respond("🎟 **مدیریت کدهای تخفیف**", buttons=[[Button.inline("باز کردن مدیریت کد تخفیف", data="discounts_open")], [Button.inline("🔙 بازگشت", data="back_to_admin_panel")]], parse_mode="md")
    elif msg == "👥 کاربران":
        await event.respond("👥 لطفاً آیدی عددی کاربر را ارسال کنید:", buttons=[[Button.text("🔙 بازگشت به پنل", resize=True)]])
        await set_step(event.sender_id, "MToUser")
    elif msg == "📝 متن‌ها و دکمه‌ها":
        await event.respond("📝 **مدیریت دکمه‌های کاربر**\n\nاز این بخش متن و ظاهر دکمه‌های منوی کاربر را تنظیم کنید.", buttons=await create_keyboard_buttons_admin_buttons(1), parse_mode="md")
    elif msg == "📝 مدیریت لاگ‌ها":
        await event.respond("📝 **مدیریت لاگ‌ها**\n\nنوع لاگ و مقصد ارسال را انتخاب کنید.", buttons=[[Button.inline("⚙️ باز کردن مدیریت لاگ‌ها", data="rep_logs_open")], [Button.inline("🔙 بازگشت", data="back_to_admin_panel")]], parse_mode="md")
    elif msg == "🔗 لینک های آماده":
        bot_username = await get_bot_username(Kenzo)
        await event.respond(format_admin_links_message(bot_username), buttons=[[Button.inline("🔙 بازگشت", data="back_to_admin_panel")]], parse_mode="md")


async def _rep_callback_handler(event: events.CallbackQuery.Event):
    if not _rep_admin(event):
        return
    data = event.data.decode("utf-8")

    if data == "rep_sales_menu":
        await _show_sales_menu(event)
        raise events.StopPropagation

    if data.startswith("rep_sales_toggle:"):
        panel = await _tenant_panel()
        if not panel:
            await event.answer("❌ پنل نماینده پیدا نشد.", alert=True)
            return
        key = data.split(":", 1)[1]
        if key == "custom":
            settings = feature_settings(panel)
            toggle_custom_buy_enabled(settings)
        elif key in {"shop", "reseller"}:
            settings = feature_settings(panel)
            toggle_panel_sales_setting(settings, "shop_enabled" if key == "shop" else "reseller_enabled")
        else:
            return
        await PanelsManager().update_panel(panel.code, feature_settings=settings)
        await event.answer("✅ تنظیمات فروش ذخیره شد.", alert=True)
        await _show_sales_menu(event)
        raise events.StopPropagation

    if data == "rep_keyboard_page:1":
        await event.edit("📝 **دکمه‌های منوی کاربر**", buttons=await create_keyboard_buttons_admin_buttons(1), parse_mode="md")
        raise events.StopPropagation

    if data == "discounts_open":
        await event.answer()
        await message_handler_discount_admin(event)
        raise events.StopPropagation

    if data == "rep_logs_open":
        await event.answer()
        await message_handler_log_admin(event)
        raise events.StopPropagation

    # Reuse the mature panel/keyboard callback implementation, but never allow
    # panel creation/deletion entry points from a representative runtime.
    if data.startswith(("panel_", "keyboard_", "keyboard_page", "edit_keyboard", "plan_", "Plan", "ManagePlans_", "PrevPlan:", "NextPlan:", "BackToPlanMainMenu")):
        blocked = ("addpanel", "add_panel", "panel_add", "delete_panel", "deletePanel")
        if any(token.lower() in data.lower() for token in blocked):
            await event.answer("⛔ ثبت یا حذف پنل در ربات نماینده مجاز نیست.", alert=True)
            raise events.StopPropagation
        await panel_admin_callback_handler(event)
        raise events.StopPropagation


def register(client):
    client.add_event_handler(_rep_menu_handler, events.NewMessage(incoming=True, func=_rep_admin))
    client.add_event_handler(_rep_callback_handler, events.CallbackQuery(func=_rep_admin))

    # Existing mature flows are reused inside the representative tenant.
    client.add_event_handler(msg_manage_user_admin, events.NewMessage(incoming=True, func=_rep_admin))
    client.add_event_handler(message_handler_discount_admin, events.NewMessage(incoming=True, func=_rep_admin))
    client.add_event_handler(message_handler_log_admin, events.NewMessage(incoming=True, func=_rep_admin))

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
from app.telegram.admin.discounts.callbacks import callback_discount_admin
from app.telegram.admin.discounts.messages import message_handler_discount_admin
from app.telegram.admin.logs.callbacks import callback_log_admin
from app.telegram.admin.logs.keyboards import main_menu_buttons as log_main_menu_buttons
from app.telegram.admin.logs.messages import message_handler_log_admin
from app.telegram.admin.manage_user.callbacks import callback_manage_user_admin
from app.telegram.admin.manage_user.messages import msg_manage_user_admin
from app.telegram.admin.panels.callbacks import panel_admin_callback_handler
from app.telegram.admin.panels.service import build_panel_summary_block, display_panels
from app.telegram.admin.plans.callbacks import inline_callback as plan_inline_callback
from app.telegram.keyboards.customization import create_keyboard_buttons_admin_buttons
from app.telegram.shared.url_presets import format_admin_links_message, get_bot_username
from app.telegram.state import set_step

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


async def _tenant_panel_code() -> int | None:
    panel = await _tenant_panel()
    return int(panel.code) if panel else None


async def _show_rep_plan_panel_selector(event, *, manage: bool) -> None:
    panel = await _tenant_panel()
    if not panel:
        await event.answer("❌ پنل نماینده پیدا نشد.", alert=True)
        return
    action = "ManagePlans" if manage else "AddPlans"
    title = "مدیریت پلن‌های پنل نماینده" if manage else "ساخت پلن برای پنل نماینده"
    buttons = [[Button.inline(f"{'✅' if panel.enable == 1 else '❌'} {panel.name}", data=f"{action}_{panel.code}")]]
    buttons.append([Button.inline("🔙 بازگشت", data="BackToPlanMainMenu")])
    await event.edit(f"🗞 **{title}**\n\nفقط پنل متصل به همین نماینده قابل انتخاب است.", buttons=buttons, parse_mode="md")


async def _show_plan_menu(event):
    await event.respond(
        "🗞 **مدیریت پلن‌ها**\n\nپلن‌ها فقط برای پنل نماینده فعلی مدیریت می‌شوند.\nثبت یا حذف پنل از این بخش مجاز نیست.",
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
        from app.telegram.admin.discounts.service import show_main_menu
        await show_main_menu(event)
        await set_step(event.sender_id, "takhfif_select")
    elif msg == "👥 کاربران":
        await event.respond("👥 لطفاً آیدی عددی کاربر را ارسال کنید:", buttons=[[Button.text("🔙 بازگشت به پنل", resize=True)]])
        await set_step(event.sender_id, "MToUser")
    elif msg == "📝 متن‌ها و دکمه‌ها":
        await event.respond("📝 **دکمه‌های منوی کاربر**\n\nمتن و ظاهر دکمه‌ها از همین بخش قابل تنظیم است.", buttons=await create_keyboard_buttons_admin_buttons(1), parse_mode="md")
    elif msg == "📝 مدیریت لاگ‌ها":
        await event.respond("📝 **مدیریت لاگ‌ها**\n\nنوع لاگ و مقصد ارسال را انتخاب کنید.", buttons=log_main_menu_buttons(), parse_mode="md")
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
        settings = feature_settings(panel)
        if key == "custom":
            toggle_custom_buy_enabled(settings)
        elif key in {"shop", "reseller"}:
            toggle_panel_sales_setting(settings, "shop_enabled" if key == "shop" else "reseller_enabled")
        else:
            return
        await PanelsManager().update_panel(panel.code, feature_settings=settings)
        await event.answer("✅ تنظیمات فروش ذخیره شد.", alert=True)
        await _show_sales_menu(event)
        raise events.StopPropagation

    if data == "PlanAddSelectPanel":
        await _show_rep_plan_panel_selector(event, manage=False)
        raise events.StopPropagation

    if data == "PlanManageSelectPanel":
        await _show_rep_plan_panel_selector(event, manage=True)
        raise events.StopPropagation

    if data.startswith("AddPlans_") or data.startswith("ManagePlans_"):
        panel_code = int(data.split("_", 1)[1])
        tenant_code = await _tenant_panel_code()
        if tenant_code is None or panel_code != tenant_code:
            await event.answer("⛔️ فقط پنل متصل به همین نماینده قابل مدیریت است.", alert=True)
            raise events.StopPropagation
        await plan_inline_callback(event)
        raise events.StopPropagation

    if data.startswith("BuyVPN_"):
        selected_code = data.removeprefix("BuyVPN_")
        tenant_code = await _tenant_panel_code()
        if tenant_code is None or str(tenant_code) != selected_code:
            await event.answer("⛔️ دسترسی به این پنل برای این نماینده مجاز نیست.", alert=True)
            raise events.StopPropagation
        return

    if data in {"addpanel", "add_panel", "panel_add", "register_panel", "delete_panel", "deletePanel"} or data.startswith(("addpanel:", "add_panel:", "panel_add:", "register_panel:", "delete_panel:", "deletePanel:")):
        await event.answer("⛔ ثبت یا حذف پنل در ربات نماینده مجاز نیست.", alert=True)
        raise events.StopPropagation

    if data == "rep_keyboard_page:1":
        await event.edit("📝 **دکمه‌های منوی کاربر**", buttons=await create_keyboard_buttons_admin_buttons(1), parse_mode="md")
        raise events.StopPropagation

    if data.startswith("discount") or data.startswith("EditDisc") or data in {"discounts", "discount_info_back"}:
        await callback_discount_admin(event)
        raise events.StopPropagation

    if data.startswith("log_") or data in {"log_management", "log_show_status", "log_set_all", "back_to_log_management"}:
        await callback_log_admin(event)
        raise events.StopPropagation

    if data.startswith(("AdminReseller_", "MToUser_", "AdminConfig", "UserInfo:", "CreateConfigFor:", "BulkDeleteConfigs:", "confirm_phone_", "bansup_", "unbansup_", "sendm_")):
        await callback_manage_user_admin(event)
        raise events.StopPropagation

    if data.startswith(("Plan", "PrevPlan:", "NextPlan:", "BackToPlanMainMenu", "plan_", "duration_", "ManagePlans_", "AddPlans_")):
        await plan_inline_callback(event)
        raise events.StopPropagation

    if data.startswith(("panel_", "keyboard_", "keyboard_page", "edit_keyboard")):
        blocked = ("addpanel", "add_panel", "panel_add", "delete_panel", "deletePanel", "panel_delete")
        if any(token.lower() in data.lower() for token in blocked):
            await event.answer("⛔ ثبت یا حذف پنل در ربات نماینده مجاز نیست.", alert=True)
            raise events.StopPropagation
        await panel_admin_callback_handler(event)
        raise events.StopPropagation


def register(client):
    client.add_event_handler(_rep_menu_handler, events.NewMessage(incoming=True, func=_rep_admin))
    client.add_event_handler(_rep_callback_handler, events.CallbackQuery(func=_rep_admin))
    client.add_event_handler(msg_manage_user_admin, events.NewMessage(incoming=True, func=_rep_admin))
    client.add_event_handler(message_handler_discount_admin, events.NewMessage(incoming=True, func=_rep_admin))
    client.add_event_handler(message_handler_log_admin, events.NewMessage(incoming=True, func=_rep_admin))

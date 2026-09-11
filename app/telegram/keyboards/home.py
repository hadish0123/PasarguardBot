"""Home reply keyboard builders."""

from app.custom_telethon.button import Button
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.user import UserCRUD
from app.runtime.context import is_runtime_admin

from .common import _get_keyboard_button_config, styled_reply_button


async def bhome_buttons(user_id, lang):
    """Build the canonical user home menu.

    The customer-facing menu is intentionally stable and always exposes the seven
    core actions. Their configured labels/styles can still be customized from the
    admin keyboard settings, but an admin cannot accidentally hide a core action
    from the home menu by disabling an unrelated feature flag.
    """
    keyboard_crud = KeyboardButtonCRUD()

    menu_buy_service, menu_buy_service_style = await _get_keyboard_button_config(
        keyboard_crud,
        "bt.menu_buy_service",
        "🛍 خرید سرویس",
        default_style="success",
        default_icon=5373052667671093676,
    )
    menu_my_services, menu_my_services_style = await _get_keyboard_button_config(
        keyboard_crud,
        "bt.menu_my_services",
        "🔑 سرویس های من",
        default_style="primary",
        default_icon=5895443668663275064,
    )
    menu_add_balance, menu_add_balance_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_add_balance", "💰 افزایش موجودی"
    )
    menu_profile, menu_profile_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_profile", "🙍 پروفایل من"
    )
    menu_support, menu_support_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_support", "☎️ پشتیبانی"
    )
    menu_help, menu_help_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_help", "📚 راهنما"
    )
    menu_advanced_settings, menu_advanced_settings_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_advanced_settings", "⚙️ تنظیمات پیشرفته"
    )
    menu_admin_panel, menu_admin_panel_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_admin_panel", "⚙️ پنل مدیریت"
    )

    # Keep the user lookup for deployments that rely on the user record being
    # initialized before rendering the home keyboard.
    await UserCRUD().read_user(user_id=user_id)

    # Canonical customer menu requested by the product:
    # خرید سرویس / سرویس های من / افزایش موجودی / پروفایل / پشتیبانی / راهنما /
    # تنظیمات پیشرفته. Keep the layout stable across central and representative
    # runtimes so both experiences behave identically.
    keyboard: list[list] = [
        [
            styled_reply_button(menu_buy_service, menu_buy_service_style),
            styled_reply_button(menu_my_services, menu_my_services_style),
        ],
        [
            styled_reply_button(menu_add_balance, menu_add_balance_style),
            styled_reply_button(menu_profile, menu_profile_style),
        ],
        [
            styled_reply_button(menu_support, menu_support_style),
            styled_reply_button(menu_help, menu_help_style),
        ],
        [styled_reply_button(menu_advanced_settings, menu_advanced_settings_style)],
    ]

    # Management access remains an additional row only for runtime admins; it is
    # never shown to ordinary customers or representatives' end users.
    if is_runtime_admin(user_id):
        keyboard.append([styled_reply_button(menu_admin_panel, menu_admin_panel_style)])

    return keyboard

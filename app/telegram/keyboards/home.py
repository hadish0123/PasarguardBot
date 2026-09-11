"""Home reply keyboard builders."""

from app.custom_telethon.button import Button
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD
from app.db.models.settings import DEFAULT_HOME_MENU_SETTINGS
from app.runtime.context import is_runtime_admin
from config import DISABLE_UPTIME_BUTTONS

from .common import _get_keyboard_button_config, styled_reply_button


def _home_menu_enabled(setting, attr: str) -> bool:
    default = bool(DEFAULT_HOME_MENU_SETTINGS.get(attr, True))
    if setting is None:
        return default
    return bool(getattr(setting, attr, default))


async def bhome_buttons(user_id, lang):
    """Build the canonical user menu used by both central and representative runtimes.

    The seven primary user actions stay consistent across tenants. Optional legacy
    reseller/trial/uptime entries are intentionally kept out of the main menu so the
    user experience remains stable and focused; their flows remain available through
    their dedicated entry points where applicable.
    """
    keyboard_crud = KeyboardButtonCRUD()
    menu_my_services, menu_my_services_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_my_services", "🔑 سرویس های من", default_style="primary", default_icon=5895443668663275064
    )
    menu_buy_service, menu_buy_service_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_buy_service", "🛍 خرید سرویس", default_style="success", default_icon=5373052667671093676
    )
    menu_profile, menu_profile_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_profile", "🙍 پروفایل من"
    )
    menu_add_balance, menu_add_balance_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_add_balance", "💰 افزایش موجودی"
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

    # Keep the user object lookup here because some deployments use it for the
    # configured home-menu conditions and future menu extensions.
    await UserCRUD().read_user(user_id=user_id)
    setting = await SettingsManager().get_settings()

    keyboard: list[list] = [
        [
            styled_reply_button(menu_buy_service, menu_buy_service_style),
            styled_reply_button(menu_my_services, menu_my_services_style),
        ],
        [
            styled_reply_button(menu_add_balance, menu_add_balance_style),
            styled_reply_button(menu_profile, menu_profile_style),
        ],
    ]

    utility_row = []
    if _home_menu_enabled(setting, "support_mode"):
        utility_row.append(styled_reply_button(menu_support, menu_support_style))
    if _home_menu_enabled(setting, "help_mode"):
        utility_row.append(styled_reply_button(menu_help, menu_help_style))
    if not DISABLE_UPTIME_BUTTONS:
        # Uptime remains intentionally available only through its existing dedicated
        # flow; it is not part of the canonical seven-button home menu.
        pass
    if utility_row:
        keyboard.append(utility_row)

    if _home_menu_enabled(setting, "advanced_settings_mode"):
        keyboard.append([styled_reply_button(menu_advanced_settings, menu_advanced_settings_style)])

    if is_runtime_admin(user_id):
        keyboard.append([styled_reply_button(menu_admin_panel, menu_admin_panel_style)])

    return keyboard

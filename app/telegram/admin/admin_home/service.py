"""Shared helpers for admin home panel."""
from app import Kenzo
from app.db.crud.log_channels import LogChannelManager
from app.runtime.context import is_representative_runtime
from app.telegram.keyboards.admin import get_panel_admin_buttons
from app.telegram.state import set_step
from config import LOG_CHANNEL

ADD_PANEL_STEPS = frozenset({"addPanel_name", "AddPanel_url", "AddPanel_auth_type", "AddPanel_username", "AddPanel_password", "AddPanel_api_key", "AddPanel_select_group", "ChangePanelAuth_username", "ChangePanelAuth_password", "ChangePanelAuth_api_key"})
_SETUP_WARNING = "⚠️ **تنظیمات ربات کامل نیست**\n\nاز بخش **📝 مدیریت لاگ‌ها** مقصد ارسال لاگ‌ها را مشخص کنید."

def _admin_home_message(user_id: int, username: str | None, *, setup_warning: str | None = None) -> str:
    user_label = username or "—"
    if is_representative_runtime():
        message = f"🏢 **پنل مدیریت نماینده**\n\n👤 شناسه: `{user_id}`\n🔹 نام کاربری: @{user_label}\n\n🔒 این پنل فقط به نمایندگی و پنل پاسارگاد متصل به همین ربات دسترسی دارد.\n"
    else:
        message = f"🌺 **پنل مدیریت**\n\n👤 شناسه: `{user_id}`\n🔹 نام کاربری: @{user_label}\n"
    if setup_warning:
        message += f"\n{setup_warning}\n"
    return message

async def send_admin_home(user_id: int, username: str | None = None) -> None:
    await set_step(user_id=user_id, step="panel")
    setup_warning = None
    if not is_representative_runtime() and LOG_CHANNEL is None:
        channels = await LogChannelManager().get_all_log_channels()
        if not any(ch.is_active for ch in channels):
            setup_warning = _SETUP_WARNING
    await Kenzo.send_message(entity=user_id, message=_admin_home_message(user_id, username, setup_warning=setup_warning), buttons=get_panel_admin_buttons(is_representative_runtime()))

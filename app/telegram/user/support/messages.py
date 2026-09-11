"""Message handlers for user support."""

from telethon import Button, events
from telethon.errors import MessageTooLongError
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.keyboards import get_button_text
from app.telegram.keyboards.common import is_keyboard_config_step, is_wizard_step
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.guards.channel_gate import ensure_channel_membership
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import get_step, set_step
from app.utils.text.bot_texts import get_bot_text
from config import ADMIN_ID


def _support_admin_lines() -> str:
    lines = []
    for admin_id in ADMIN_ID:
        lines.append(f"👤 <a href='tg://user?id={admin_id}'>پشتیبانی</a> — <code>{admin_id}</code>")
    return "\n".join(lines) or "پشتیبانی در دسترس نیست."


async def support_menu_filter(event: Message) -> bool:
    if event.is_channel or is_wizard_step(await get_step(event.sender_id)) or is_keyboard_config_step(await get_step(event.sender_id)):
        return False
    msg = event.message.text or ""
    support_text = await get_button_text("bt.menu_support", "☎️ پشتیبانی")
    return msg in {support_text, "☎️ پشتیبانی", "/support"}


@bot_is_offline
async def support_menu(event: Message):
    if not await ensure_channel_membership(event):
        raise events.StopPropagation
    support_text = await get_bot_text(
        key="support_message",
        default="👈🏻 جهت ارتباط مستقیم با پشتیبانی:\n{support_admins}\n\n🗯 سؤال، پیشنهاد، مشکل و یا انتقاد خود را در قالب یک پیام متنی واحد و کامل ارسال کنید:",
        lang="fa",
    )
    support_text = support_text.replace("{support_admins}", _support_admin_lines())
    # Replace the old hard-coded support handle in existing tenant text too.
    if "@AmirKenzoo" in support_text:
        support_text = support_text.replace("@AmirKenzoo", _support_admin_lines())
    await event.respond(support_text, buttons=[Button.text(text="🏠 بازگشت", resize=True, single_use=True)])
    await set_step(event.sender_id, "support")
    raise events.StopPropagation


async def is_support_message(event: Message) -> bool:
    if not event.message.text or await get_step(event.sender_id) != "support":
        return False
    msg = event.message.text
    commands = ("/start", "/panel", "/support", "/help", "/buy", "/charge", "/myconfigs", "/mywallet", "/games", "/dice", "/listapps")
    if msg.startswith(commands):
        return False
    button_keys = [
        "bt.menu_add_balance", "bt.menu_admin_panel", "bt.menu_advanced_settings", "bt.menu_buy_service",
        "bt.menu_get_trial", "bt.menu_help", "bt.menu_my_services", "bt.menu_profile", "bt.menu_support", "bt.menu_uptime",
    ]
    defaults = {
        "bt.menu_add_balance": "💰 افزایش موجودی", "bt.menu_admin_panel": "⚙️ پنل مدیریت", "bt.menu_advanced_settings": "⚙️ تنظیمات پیشرفته",
        "bt.menu_buy_service": "🛍 خرید سرویس", "bt.menu_get_trial": "🎁 دریافت تست", "bt.menu_help": "📚 راهنما",
        "bt.menu_my_services": "🔑 سرویس های من", "bt.menu_profile": "🙍 پروفایل من", "bt.menu_support": "☎️ پشتیبانی", "bt.menu_uptime": "🔋 وضعیت سرویس ها",
    }
    button_texts = tuple([await get_button_text(key, defaults[key]) for key in button_keys])
    other_texts = ("☎️", "🏠", "🏠 بازگشت", "🛍 خرید سرویس", "🔑 سرویس های من", "💰 افزایش موجودی", "🙍 پروفایل من", "📚 راهنما", "⚙️ تنظیمات پیشرفته", "🔙 بازگشت به پنل")
    if msg in button_texts or msg in other_texts:
        return False
    return not msg.startswith(("☎️", "🏠", "/"))


@bot_is_offline
async def support_message(event: Message):
    msg = event.message.text
    from_id = event.sender_id
    sender = await event.get_sender()
    first_name = getattr(sender, "first_name", None) or "کاربر"
    if not msg or len(msg) > 600:
        await event.reply("⚠️ فقط پیام متنی با طول حداکثر 600 کاراکتر ارسال کنید.")
        return
    try:
        for admin_id in ADMIN_ID:
            await Kenzo.send_message(
                admin_id,
                f"🏷 پیام جدید | کاربر <a href='tg://user?id={from_id}'>{first_name}</a>\n\n➖ فرستنده(ID): <code>{from_id}</code>\n\n📝 متن پیام ارسالی:\n\n{msg}",
                buttons=[[Button.inline("⛔️ مسدود کردن", f"bansup_{from_id}"), Button.inline("📨 پاسخ به کاربر", f"sendm_{from_id}")]],
                parse_mode="html",
            )
        await event.reply("💬 پیام شما با موفقیت به پشتیبانی ارسال شد.", buttons=await bhome_buttons(event.sender_id, "fa"))
        await set_step(event.sender_id, "home")
        raise events.StopPropagation
    except MessageTooLongError:
        await event.reply("⚠️ پیام شما بیش از حد طولانی است. لطفا پیام کوتاه‌تری ارسال کنید.")


def register(client):
    client.add_event_handler(support_menu, events.NewMessage(incoming=True, func=support_menu_filter))
    client.add_event_handler(support_message, events.NewMessage(incoming=True, func=is_support_message))

from __future__ import annotations

from telethon import Button, events

from app.core.ids import USER_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
from app.services.user_profile import SERVICE

PREFIX = b"user:profile:"


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await allowed(event):
                return await event.answer("دسترسی به این بخش ندارید.", alert=True)
            await render_callback(event)
    client.add_event_handler(callback, events.CallbackQuery(data=PREFIX))


async def allowed(event):
    if not event.is_private or not get_tenant():
        return False
    user = await USERS.get_by_telegram_id(event.sender_id)
    return bool(user and not user.blocked)


async def render_profile(telegram_user_id: int):
    user = await SERVICE.get(telegram_user_id)
    if user is None:
        return "👤 **پروفایل من**\n\nاطلاعات کاربری پیدا نشد.", [[Button.inline("🔙 فروشگاه", b"user:" + USER_HOME.encode())]]
    username = f"@{user.username}" if user.username else "ندارد"
    name = " ".join(x for x in (user.first_name, user.last_name) if x) or "ثبت نشده"
    text = (
        "👤 **پروفایل من**\n\n"
        f"🆔 شناسه تلگرام: `{user.telegram_user_id}`\n"
        f"👤 نام: **{name}**\n"
        f"🔹 نام کاربری: **{username}**\n"
        f"💰 موجودی: **{user.balance:,.2f}**"
    )
    buttons = [
        [Button.inline("✏️ ویرایش نام", PREFIX + b"edit_name")],
        [Button.inline("🔄 بروزرسانی", PREFIX + b"show")],
        [Button.inline("🔙 فروشگاه", b"user:" + USER_HOME.encode())],
    ]
    return text, buttons


async def render_callback(event):
    action = event.data[len(PREFIX):].decode(errors="ignore")
    if action in ("", "show"):
        text, buttons = await render_profile(event.sender_id)
        await event.edit(text, buttons=buttons)
        return await event.answer()
    if action == "edit_name":
        await event.edit("✏️ **ویرایش نام**\n\nنام جدید را در پیام بعدی ارسال کنید.\n\nبرای لغو: `/cancel`", buttons=[[Button.inline("🔙 انصراف", PREFIX + b"show")]])
        return await event.answer()
    await event.answer("گزینه نامعتبر است.", alert=True)


async def handle_message(event):
    if not event.is_private or not get_tenant():
        return
    user = await USERS.get_by_telegram_id(event.sender_id)
    if not user or user.blocked:
        return
    text = (event.raw_text or "").strip()
    if text == "/cancel":
        from app.telegram.representative.user import customer_menu
        return await event.respond("عملیات لغو شد.", buttons=await customer_menu())

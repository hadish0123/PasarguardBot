from __future__ import annotations

from urllib.parse import quote

from telethon import Button, events

from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.logs import SERVICE as LOGS
from app.services.referrals import SERVICE
from app.services.representative_users import SERVICE as USERS

PREFIX = b"user:referral"
ROOT_CALLBACK = PREFIX
REFRESH_CALLBACK = PREFIX + b":refresh"
HOME_CALLBACK = b"user:home"


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await allowed(event):
                return await event.answer("دسترسی به این بخش را ندارید.", alert=True)
            await event.answer()
            try:
                await render_callback(event)
            except Exception:
                await LOGS.add("referral.render.error", "callback render failed", event.sender_id)
                await event.respond("❌ خطایی در نمایش بخش دعوت دوستان رخ داد. دوباره تلاش کنید.")

    client.add_event_handler(
        callback,
        events.CallbackQuery(
            func=lambda e: bool(e.data and (e.data == ROOT_CALLBACK or e.data.startswith(PREFIX + b":")))
        ),
    )


async def allowed(event):
    if not event.is_private or not get_tenant():
        return False
    user = await USERS.get_by_telegram_id(event.sender_id)
    return bool(user and not user.blocked)


async def render(event):
    code = f"R{event.sender_id}"
    count = await SERVICE.stats(event.sender_id)
    me = await event.client.get_me()
    username = (getattr(me, "username", None) or "").strip()
    buttons = []

    if username:
        invite_url = f"https://t.me/{username}?start=ref_{event.sender_id}"
        share_text = "🎁 با لینک دعوت من وارد ربات شو و از خدمات فروشگاه استفاده کن."
        share_url = (
            "https://t.me/share/url?url="
            + quote(invite_url, safe="")
            + "&text="
            + quote(share_text, safe="")
        )
        buttons.append([Button.url("📨 اشتراک‌گذاری لینک دعوت", share_url)])
        buttons.append([Button.url("🔗 باز کردن لینک دعوت", invite_url)])

    buttons += [
        [Button.inline("🔄 بروزرسانی", REFRESH_CALLBACK)],
        [Button.inline("🔙 فروشگاه", HOME_CALLBACK)],
    ]

    text = (
        "👥 **دعوت دوستان**\n\n"
        f"🎟 کد دعوت شما: `{code}`\n"
        f"👤 تعداد دعوت‌های ثبت‌شده: **{count}**\n\n"
    )
    if username:
        text += (
            "🎁 با اشتراک‌گذاری لینک زیر، کاربر جدید هنگام اولین ورود به ربات به دعوت شما ثبت می‌شود.\n"
            "🔒 هر کاربر فقط یک‌بار به یک دعوت‌کننده متصل می‌شود."
        )
    else:
        text += "⚠️ برای ساخت لینک دعوت، ابتدا باید برای ربات نماینده یک نام کاربری عمومی تنظیم شود."

    return await event.edit(text, buttons=buttons)


async def render_callback(event):
    raw = event.data[len(PREFIX):].decode(errors="ignore")
    action = raw.lstrip(":")
    if action in ("", "refresh"):
        return await render(event)
    return await event.answer("گزینه نامعتبر است.", alert=True)

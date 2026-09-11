from __future__ import annotations

from telethon import Button


ADMIN_MENU = [
    [Button.inline("📊 داشبورد", b"rep:dashboard")],
    [Button.inline("🗂 مدیریت پلن‌ها", b"rep:plans"), Button.inline("👥 کاربران", b"rep:users")],
    [Button.inline("🛒 فروش و سفارش‌ها", b"rep:orders")],
    [Button.inline("🎟 تخفیف‌ها", b"rep:discounts"), Button.inline("⚙️ تنظیمات فروش", b"rep:sales")],
    [Button.inline("📝 متن‌ها و دکمه‌ها", b"rep:texts")],
    [Button.inline("📋 لاگ‌ها", b"rep:logs"), Button.inline("🔗 لینک‌ها", b"rep:links")],
    [Button.inline("⚙️ تنظیمات نماینده", b"rep:settings")],
]


async def show_admin(event) -> None:
    await event.respond("🛠 **پنل مدیریت نماینده**", buttons=ADMIN_MENU)

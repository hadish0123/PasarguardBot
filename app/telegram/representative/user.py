from __future__ import annotations

from telethon import Button


USER_MENU = [
    [Button.inline("🛒 خرید سرویس", b"user:buy")],
    [Button.inline("📦 سرویس‌های من", b"user:services"), Button.inline("💳 کیف پول", b"user:wallet")],
    [Button.inline("👤 پروفایل", b"user:profile"), Button.inline("🎁 دعوت دوستان", b"user:referral")],
    [Button.inline("🎟 کد تخفیف", b"user:discount"), Button.inline("🎁 سرویس آزمایشی", b"user:trial")],
    [Button.inline("🆘 پشتیبانی", b"user:support")],
]


async def show_home(event) -> None:
    await event.respond("🏪 **فروشگاه**\n\nیکی از گزینه‌های زیر را انتخاب کنید.", buttons=USER_MENU)

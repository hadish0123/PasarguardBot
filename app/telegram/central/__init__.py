from __future__ import annotations

from telethon import events

from app.core.config import settings
from app.services.registration import RegistrationService


def menu():
    from telethon import Button
    return [[Button.inline("🤖 ثبت ربات نمایندگی", b"central:register")], [Button.inline("🔎 پیگیری درخواست", b"central:track")]]


def register_central_handlers(client) -> None:
    client.add_event_handler(start, events.NewMessage(pattern=r"^/start$"))
    client.add_event_handler(register, events.CallbackQuery(data=b"central:register"))
    client.add_event_handler(track, events.CallbackQuery(data=b"central:track"))


async def start(event):
    await event.respond("🌐 **سامانه مرکزی نمایندگان**\n\nثبت، پیگیری و مدیریت ربات نمایندگی از اینجا انجام می‌شود.", buttons=menu())


async def register(event):
    await event.answer()
    await event.edit("1️⃣ **ثبت نمایندگی**\n\nنام برند خود را ارسال کنید.")


async def track(event):
    await event.answer()
    await event.edit("🔎 **پیگیری درخواست**\n\nکد پیگیری خود را ارسال کنید.", buttons=menu())

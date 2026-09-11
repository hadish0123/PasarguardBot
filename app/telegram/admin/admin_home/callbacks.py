"""Callback handlers for admin home panel."""

import contextlib

from telethon import events

from app.runtime.context import is_runtime_admin
from app.telegram.admin.admin_home.service import send_admin_home


async def callback_back_to_admin_panel(event: events.CallbackQuery.Event):
    if not event.is_private or not is_runtime_admin(event.sender_id):
        return
    await event.answer()
    with contextlib.suppress(Exception):
        await event.delete()
    await send_admin_home(event.sender_id)
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        callback_back_to_admin_panel,
        events.CallbackQuery(data="back_to_admin_panel", func=lambda e: is_runtime_admin(e.sender_id)),
    )

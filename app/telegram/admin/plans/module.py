"""Package entry point for the admin plans module."""

from telethon import Button, events

from app.runtime.context import is_runtime_admin, is_representative_runtime
from app.telegram.admin.plans import callbacks, messages

MODULE_NAME = "admin.plans"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "Admin plan management flow"

_registered_clients: set[int] = set()


async def representative_plan_menu_entry(event):
    """Open the existing plan-management menu from the representative home button."""
    if not event.is_private or not is_representative_runtime():
        return
    if not is_runtime_admin(event.sender_id):
        return
    msg = (getattr(event.message, "text", None) or "").strip()
    if msg != "🗞 مدیریت پلن‌ها":
        return
    buttons = [
        [Button.inline("➕ ساخت پلن جدید", data="PlanAddSelectPanel")],
        [Button.inline("📋 مدیریت پلن‌ها", data="PlanManageSelectPanel")],
        [Button.inline("❌ بستن منو ❌", data="DataCancelPlans")],
    ]
    await event.respond("یکی از گزینه‌های زیر را انتخاب کنید:", buttons=buttons)


def register_representative_entry(client):
    client.add_event_handler(
        representative_plan_menu_entry,
        events.NewMessage(incoming=True),
    )


def setup(client):
    client_id = id(client)
    if client_id in _registered_clients:
        return
    messages.register(client)
    callbacks.register(client)
    register_representative_entry(client)
    _registered_clients.add(client_id)

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


async def representative_plan_message_entry(event):
    """Route representative plan-creation text into the existing plan handler.

    The legacy plans message registration is restricted to ADMIN_ID, while a
    representative runtime uses the tenant owner as its admin. Keep the
    existing plan flow intact and run this routing handler before other broad
    representative message handlers so numeric wizard input cannot be missed.
    """
    if not event.is_private or not is_representative_runtime():
        return
    if not is_runtime_admin(event.sender_id):
        return

    msg = (getattr(event.message, "text", None) or "").strip()
    if not msg:
        return

    step = await messages.get_step(event.sender_id)
    if step in {"addPlan_1", "addPlan_2", "addPlan_3", "addPlan_4"}:
        await messages.message_handler_plans(event)


def register_representative_entry(client):
    # Plan wizard input must run before the generic representative message
    # handlers. Telethon-compatible custom dispatchers sort lower priorities
    # first, so use a dedicated early priority without changing the flow.
    handler = events.NewMessage(incoming=True)
    handler._handler_priority = -100
    client.add_event_handler(representative_plan_message_entry, handler)

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

from __future__ import annotations

from telethon import Button, events

from app.core.ids import REP_HOME, REP_TEXTS
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.texts import SERVICE, LABELS

PREFIX = b"rep:texts:"
INPUTS: dict[tuple[str, int], str] = {}


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await _authorized(event):
                return await event.answer("دسترسی مدیریت ندارید.", alert=True)
            await handle(event)

    async def message(event):
        async with tenant_dispatch(tenant_id):
            if not await _authorized(event):
                return
            key = (get_tenant(), event.sender_id)
            field = INPUTS.get(key)
            if not field:
                return
            value = (event.raw_text or "").strip()
            if value.lower() in {"/cancel", "لغو"}:
                INPUTS.pop(key, None)
                text, buttons = await render()
                return await event.respond(text, buttons=buttons)
            try:
                await SERVICE.set(field, value)
                INPUTS.pop(key, None)
                text, buttons = await detail(field)
                await event.respond("✅ متن با موفقیت ذخیره شد.", buttons=buttons)
            except ValueError as exc:
                await event.respond(f"❌ {exc}\n\nدوباره ارسال کنید یا `لغو` بفرستید.")

    client.add_event_handler(
        callback,
        events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))),
    )
    client.add_event_handler(
        callback,
        events.CallbackQuery(data=b"rep:" + REP_TEXTS.encode()),
    )
    client.add_event_handler(message, events.NewMessage(incoming=True))


async def _authorized(event):
    return bool(
        event.is_private
        and get_tenant()
        and await RepresentativeDashboardService().is_owner(event.sender_id)
    )


async def render():
    rows = []
    for key, label in LABELS.items():
        rows.append([Button.inline(label, PREFIX + b"view:" + key.encode())])
    rows.append([Button.inline("📊 داشبورد", b"rep:" + REP_HOME.encode())])
    return "📝 **متن‌ها و دکمه‌ها**\n\nیک مورد را برای مشاهده و ویرایش انتخاب کنید.", rows


async def detail(key):
    values = await SERVICE.all()
    return (
        f"📝 **{LABELS[key]}**\n\n`{key}`\n\n{values[key]}",
        [
            [
                Button.inline("✏️ ویرایش", PREFIX + b"edit:" + key.encode()),
                Button.inline("♻️ بازنشانی", PREFIX + b"reset_prompt:" + key.encode()),
            ],
            [Button.inline("🔙 فهرست", PREFIX + b"list")],
        ],
    )


async def handle(event):
    action = event.data[len(PREFIX):].decode(errors="ignore")
    key = (get_tenant(), event.sender_id)

    if action == "list":
        text, buttons = await render()
        await event.edit(text, buttons=buttons)
        return await event.answer()

    if action.startswith("view:"):
        name = action[5:]
        if name not in LABELS:
            return await event.answer("مورد نامعتبر است.", alert=True)
        text, buttons = await detail(name)
        await event.edit(text, buttons=buttons)
        return await event.answer()

    if action.startswith("edit:"):
        name = action[5:]
        if name not in LABELS:
            return await event.answer("مورد نامعتبر است.", alert=True)
        INPUTS[key] = name
        return await event.edit(
            f"✏️ **ویرایش {LABELS[name]}**\n\n"
            "متن جدید را ارسال کنید.\n"
            "برای لغو `/cancel` یا `لغو` را بفرستید.",
            buttons=[[Button.inline("❌ لغو", PREFIX + b"list")]],
        )

    if action.startswith("reset_prompt:"):
        name = action[13:]
        if name not in LABELS:
            return await event.answer("مورد نامعتبر است.", alert=True)
        return await event.edit(
            f"⚠️ بازنشانی **{LABELS[name]}** انجام شود؟\n\n"
            "مقدار سفارشی حذف و متن پیش‌فرض فعال می‌شود.",
            buttons=[
                [Button.inline("✅ بله، بازنشانی", PREFIX + b"reset:" + name.encode())],
                [Button.inline("❌ انصراف", PREFIX + b"view:" + name.encode())],
            ],
        )

    if action.startswith("reset:"):
        name = action[6:]
        if name not in LABELS:
            return await event.answer("مورد نامعتبر است.", alert=True)
        await SERVICE.reset(name)
        text, buttons = await detail(name)
        await event.edit(text, buttons=buttons)
        return await event.answer("بازنشانی شد.")

    return await event.answer("گزینه نامعتبر است.", alert=True)

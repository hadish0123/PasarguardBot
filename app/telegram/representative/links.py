from __future__ import annotations

from telethon import Button, events

from app.core.ids import REP_HOME, REP_LINKS
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.links import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService

PREFIX = b"rep:links:"
INPUTS: dict[tuple[str, int], dict[str, object]] = {}


def register(client, tenant_id=None):
    async def cb(event):
        async with tenant_dispatch(tenant_id):
            if not await _auth(event):
                return await event.answer("دسترسی مدیریت ندارید.", alert=True)
            await handle(event)

    async def msg(event):
        async with tenant_dispatch(tenant_id):
            if not await _auth(event):
                return
            await handle_message(event)

    client.add_event_handler(
        cb,
        events.CallbackQuery(func=lambda e: bool(e.data and (e.data.startswith(PREFIX) or e.data == b"rep:" + REP_LINKS.encode()))),
    )
    client.add_event_handler(msg, events.NewMessage(incoming=True))


async def _auth(event):
    return bool(event.is_private and get_tenant() and await RepresentativeDashboardService().is_owner(event.sender_id))


async def render():
    rows = await SERVICE.list()
    text = "🔗 **لینک‌های آماده**\n\n" + ("هنوز لینکی ثبت نشده است." if not rows else "\n\n".join(
        f"• #{r.id} — **{r.title}**\n  🔗 {r.url}\n  🏷 نوع: `{r.kind}`" for r in rows
    ))
    buttons = [[Button.inline("➕ افزودن لینک", PREFIX + b"add")]]
    for r in rows:
        buttons.append([
            Button.inline(f"✏️ #{r.id}", PREFIX + f"edit:{r.id}".encode()),
            Button.inline(f"🗑 #{r.id}", PREFIX + f"delete_prompt:{r.id}".encode()),
        ])
    buttons.append([Button.inline("📊 داشبورد", b"rep:" + REP_HOME.encode())])
    return text, buttons


async def handle(event):
    data = event.data or b""
    action = data[len(PREFIX):].decode(errors="ignore") if data.startswith(PREFIX) else ""
    key = (get_tenant(), event.sender_id)
    if data == b"rep:" + REP_LINKS.encode() or action == "list":
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer()
    if action == "add":
        INPUTS[key] = {"step": "title"}
        return await event.edit("➕ **افزودن لینک**\n\nعنوان لینک را ارسال کنید.\nبرای لغو `/cancel`", buttons=[[Button.inline("❌ لغو", PREFIX + b"list")]])
    if action.startswith("edit:"):
        try: link_id = int(action.split(":", 1)[1])
        except ValueError: return await event.answer("شناسه نامعتبر است.", alert=True)
        row = await SERVICE.get(link_id)
        if not row: return await event.answer("لینک پیدا نشد.", alert=True)
        INPUTS[key] = {"step": "edit_title", "link_id": row.id, "title": row.title, "url": row.url, "kind": row.kind}
        return await event.edit(f"✏️ عنوان جدید را ارسال کنید.\n\nفعلی: **{row.title}**", buttons=[[Button.inline("❌ لغو", PREFIX + f"view:{row.id}".encode())]])
    if action.startswith("view:"):
        try: link_id = int(action.split(":", 1)[1])
        except ValueError: return await event.answer("شناسه نامعتبر است.", alert=True)
        row = await SERVICE.get(link_id)
        if not row: return await event.answer("لینک پیدا نشد.", alert=True)
        return await event.edit(f"🔗 **{row.title}**\n\nآدرس: {row.url}\nنوع: `{row.kind}`", buttons=[[Button.inline("✏️ ویرایش", PREFIX + f"edit:{row.id}".encode())], [Button.inline("🗑 حذف", PREFIX + f"delete_prompt:{row.id}".encode())], [Button.inline("🔙 فهرست", PREFIX + b"list")]])
    if action.startswith("delete_prompt:"):
        try: link_id = int(action.split(":", 1)[1])
        except ValueError: return await event.answer("شناسه نامعتبر است.", alert=True)
        row = await SERVICE.get(link_id)
        if not row: return await event.answer("لینک پیدا نشد.", alert=True)
        return await event.edit(f"⚠️ حذف لینک **{row.title}** انجام شود؟", buttons=[[Button.inline("✅ حذف", PREFIX + f"delete:{row.id}".encode()), Button.inline("❌ انصراف", PREFIX + f"view:{row.id}".encode())]])
    if action.startswith("delete:"):
        try: await SERVICE.delete(int(action.split(":", 1)[1]))
        except LookupError: return await event.answer("لینک پیدا نشد.", alert=True)
        t, b = await render(); await event.edit(t, buttons=b); return await event.answer("حذف شد.")
    return await event.answer("گزینه نامعتبر است.", alert=True)


async def handle_message(event):
    key = (get_tenant(), event.sender_id)
    state = INPUTS.get(key)
    if not state or not event.raw_text:
        return
    text = event.raw_text.strip()
    if text in {"/cancel", "لغو"}:
        INPUTS.pop(key, None); t, b = await render(); return await event.respond("❌ عملیات لغو شد.", buttons=b)
    try:
        step = state["step"]
        if step in {"title", "edit_title"}:
            if not 1 <= len(text) <= 120: raise ValueError("عنوان باید بین 1 تا 120 کاراکتر باشد.")
            state["title"] = text; state["step"] = "url"
            return await event.respond("🔗 آدرس لینک را ارسال کنید.")
        if step == "url":
            if not (text.startswith("http://") or text.startswith("https://")): raise ValueError("لینک باید با http:// یا https:// شروع شود.")
            if len(text) > 1000: raise ValueError("لینک بیش از حد طولانی است.")
            state["url"] = text; state["step"] = "kind"
            return await event.respond("🏷 نوع لینک را وارد کنید. مثال: `support` یا `shop`\nبرای نوع عمومی: `general`")
        if step == "kind":
            if not text or len(text) > 40: raise ValueError("نوع لینک نامعتبر است.")
            state["kind"] = text
            if state.get("link_id"):
                row = await SERVICE.update(int(state["link_id"]), str(state["title"]), str(state["url"]), str(state["kind"]))
                INPUTS.pop(key, None); return await event.respond(f"✅ لینک **{row.title}** بروزرسانی شد.")
            row = await SERVICE.create(str(state["title"]), str(state["url"]), str(state["kind"]))
            INPUTS.pop(key, None); return await event.respond(f"✅ لینک **{row.title}** ذخیره شد.")
    except ValueError as exc:
        await event.respond(f"❌ {exc}\n\nدوباره ارسال کنید یا `/cancel` بزنید.")

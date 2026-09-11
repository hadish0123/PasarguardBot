from __future__ import annotations

from telethon import Button, events
from app.core.ids import REP_HOME, REP_LOGS
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.logs import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService

PREFIX = b"rep:logs:"
PAGE_SIZE = 12


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await _authorized(event):
                return await event.answer("دسترسی مدیریت ندارید.", alert=True)
            if event.data == b"rep:" + REP_LOGS.encode() or event.data.startswith(PREFIX):
                await render_into(event)
                return
            await event.answer("گزینه نامعتبر است.", alert=True)

    client.add_event_handler(
        callback,
        events.CallbackQuery(func=lambda e: bool(e.data and (e.data.startswith(PREFIX) or e.data == b"rep:" + REP_LOGS.encode()))),
    )


async def _authorized(event):
    return bool(event.is_private and get_tenant() and await RepresentativeDashboardService().is_owner(event.sender_id))


async def render(page: int = 0):
    page = max(0, int(page))
    rows, has_next = await SERVICE.list(limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    if not rows:
        text = "📋 **لاگ‌های نماینده**\n\n" + ("هنوز رویدادی ثبت نشده است." if page == 0 else "این صفحه خالی است.")
    else:
        blocks = [f"📋 **لاگ‌های نماینده** — صفحه {page + 1}", ""]
        for row in rows:
            actor = f"👤 {row.actor_id}" if row.actor_id else "🤖 سیستم"
            details = f"\n  {row.details}" if row.details else ""
            timestamp = row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else "-"
            blocks.append(f"• #{row.id} — **{row.action}**\n  {actor} · 🕒 {timestamp}{details}")
        text = "\n\n".join(blocks)
    nav = []
    if page > 0:
        nav.append(Button.inline("◀️ قبلی", PREFIX + f"page:{page - 1}".encode()))
    if has_next:
        nav.append(Button.inline("بعدی ▶️", PREFIX + f"page:{page + 1}".encode()))
    buttons = []
    if nav:
        buttons.append(nav)
    buttons.append([Button.inline("🔄 بروزرسانی", PREFIX + f"page:{page}".encode())])
    buttons.append([Button.inline("📊 داشبورد", b"rep:" + REP_HOME.encode())])
    return text, buttons


async def render_into(event):
    action = event.data[len(PREFIX):].decode(errors="ignore") if event.data.startswith(PREFIX) else "page:0"
    try:
        page = int(action.split(":", 1)[1]) if action.startswith("page:") else 0
    except (ValueError, IndexError):
        return await event.answer("صفحه نامعتبر است.", alert=True)
    text, buttons = await render(page)
    await event.edit(text, buttons=buttons)
    await event.answer()

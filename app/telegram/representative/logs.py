from __future__ import annotations
from telethon import Button,events
from app.core.ids import REP_HOME,REP_LOGS
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.logs import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService
PREFIX=b"rep:logs:"
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):
   if not await _authorized(event):return await event.answer("دسترسی مدیریت ندارید.",alert=True)
   if event.data==b"rep:"+REP_LOGS.encode() or event.data.startswith(PREFIX): await render_into(event); return
   await event.answer("گزینه نامعتبر است.",alert=True)
 client.add_event_handler(callback,events.CallbackQuery(func=lambda e: bool(e.data and (e.data.startswith(PREFIX) or e.data==b"rep:"+REP_LOGS.encode()))))
async def _authorized(event):return bool(event.is_private and get_tenant() and await RepresentativeDashboardService().is_owner(event.sender_id))
async def render():
 rows=await SERVICE.list()
 if not rows:text="📋 **لاگ‌ها**\n\nهنوز رویدادی ثبت نشده است."
 else:text="📋 **لاگ‌های نماینده**\n\n"+"\n".join(f"• #{r.id} — **{r.action}**\n  {r.details}" for r in rows)
 return text,[[Button.inline("🔄 بروزرسانی",PREFIX+b"list")],[Button.inline("📊 داشبورد",b"rep:"+REP_HOME.encode())]]
async def render_into(event):t,b=await render();await event.edit(t,buttons=b);await event.answer()

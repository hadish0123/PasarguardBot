from __future__ import annotations
from telethon import Button,events
from app.core.ids import REP_HOME,REP_LINKS
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.links import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService
PREFIX=b"rep:links:"; INPUTS={}
def register(client,tenant_id=None):
 async def cb(event):
  async with tenant_dispatch(tenant_id):
   if not await _auth(event):return await event.answer("دسترسی مدیریت ندارید.",alert=True)
   await handle(event)
 async def msg(event):
  async with tenant_dispatch(tenant_id):
   if not await _auth(event):return
   key=(get_tenant(),event.sender_id); step=INPUTS.get(key)
   if not step:return
   if event.raw_text.strip()=="/cancel":INPUTS.pop(key,None);t,b=await render();return await event.respond(t,buttons=b)
   parts=step.split(":",1)
   try:
    if parts[0]=="title":INPUTS[key]="url:"+event.raw_text.strip();return await event.respond("🔗 آدرس لینک را ارسال کنید:")
    await SERVICE.create(parts[1],event.raw_text.strip());INPUTS.pop(key,None);t,b=await render();await event.respond("✅ لینک ذخیره شد.",buttons=b)
   except ValueError as exc:await event.respond(f"❌ {exc}")
 client.add_event_handler(cb,events.CallbackQuery(func=lambda e: bool(e.data and (e.data.startswith(PREFIX) or e.data==b"rep:"+REP_LINKS.encode()))));client.add_event_handler(msg,events.NewMessage(incoming=True))
async def _auth(event):return bool(event.is_private and get_tenant() and await RepresentativeDashboardService().is_owner(event.sender_id))
async def render():
 rows=await SERVICE.list();text="🔗 **لینک‌های آماده**\n\n"+("هنوز لینکی ثبت نشده است." if not rows else "\n".join(f"• #{r.id} — **{r.title}**\n  {r.url}" for r in rows));buttons=[[Button.inline("➕ افزودن لینک",PREFIX+b"add")]]
 for r in rows:buttons.append([Button.inline(f"🗑 حذف #{r.id}",PREFIX+f"delete:{r.id}".encode())])
 buttons.append([Button.inline("📊 داشبورد",b"rep:"+REP_HOME.encode())]);return text,buttons
async def handle(event):
 action=event.data[len(PREFIX):].decode(errors="ignore") if event.data.startswith(PREFIX) else "";key=(get_tenant(),event.sender_id)
 if event.data==b"rep:"+REP_LINKS.encode():t,b=await render();return await event.edit(t,buttons=b)
 if action=="add":INPUTS[key]="title";return await event.edit("➕ عنوان لینک را ارسال کنید:\nبرای لغو `/cancel`",buttons=[[Button.inline("❌ لغو",PREFIX+b"list")]])
 if action=="list":t,b=await render();return await event.edit(t,buttons=b)
 if action.startswith("delete:"):
  try:await SERVICE.delete(int(action[7:]));t,b=await render();await event.edit(t,buttons=b);return await event.answer("حذف شد.")
  except LookupError:return await event.answer("لینک پیدا نشد.",alert=True)
 return await event.answer("گزینه نامعتبر است.",alert=True)

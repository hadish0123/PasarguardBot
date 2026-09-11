from __future__ import annotations
from telethon import Button, events
from app.core.ids import REP_HOME,REP_TEXTS
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.texts import SERVICE,LABELS
PREFIX=b"rep:texts:"
INPUTS={}

def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):
   if not await _authorized(event): return await event.answer("دسترسی مدیریت ندارید.",alert=True)
   await handle(event)
 async def message(event):
  async with tenant_dispatch(tenant_id):
   if not await _authorized(event): return
   key=(get_tenant(),event.sender_id); field=INPUTS.get(key)
   if not field:return
   if event.raw_text.strip()=="/cancel": INPUTS.pop(key,None); t,b=await render(); return await event.respond(t,buttons=b)
   try:
    await SERVICE.set(field,event.raw_text); INPUTS.pop(key,None); t,b=await detail(field); await event.respond("✅ متن ذخیره شد.",buttons=b)
   except ValueError as exc: await event.respond(f"❌ {exc}\n\nدوباره ارسال کنید.")
 client.add_event_handler(callback,events.CallbackQuery(data=PREFIX)); client.add_event_handler(callback,events.CallbackQuery(data=b"rep:"+REP_TEXTS.encode())); client.add_event_handler(message,events.NewMessage(incoming=True))
async def _authorized(event): return bool(event.is_private and get_tenant() and await RepresentativeDashboardService().is_owner(event.sender_id))
async def render():
 vals=await SERVICE.all(); rows=[]
 for key,label in LABELS.items(): rows.append([Button.inline(label,PREFIX+b"view:"+key.encode())])
 rows.append([Button.inline("📊 داشبورد",b"rep:"+REP_HOME.encode())])
 return "📝 **متن‌ها و دکمه‌ها**\n\nیک مورد را برای مشاهده و ویرایش انتخاب کنید.",rows
async def detail(key):
 vals=await SERVICE.all(); label=LABELS[key]; value=vals[key]
 return f"📝 **{label}**\n\n`{key}`\n\n{value}",[[Button.inline("✏️ ویرایش",PREFIX+b"edit:"+key.encode()),Button.inline("♻️ بازنشانی",PREFIX+b"reset:"+key.encode())],[Button.inline("🔙 فهرست",PREFIX+b"list")]]
async def handle(event):
 action=event.data[len(PREFIX):].decode(errors="ignore"); key=(get_tenant(),event.sender_id)
 if action=="list": t,b=await render(); await event.edit(t,buttons=b); return await event.answer()
 if action.startswith("view:"):
  name=action[5:];
  if name not in LABELS:return await event.answer("مورد نامعتبر است.",alert=True)
  t,b=await detail(name); await event.edit(t,buttons=b); return await event.answer()
 if action.startswith("edit:"):
  name=action[5:]
  if name not in LABELS:return await event.answer("مورد نامعتبر است.",alert=True)
  INPUTS[key]=name; return await event.edit(f"✏️ **ویرایش {LABELS[name]}**\n\nمتن جدید را ارسال کنید.\nبرای لغو `/cancel` را بفرستید.",buttons=[[Button.inline("❌ لغو",PREFIX+b"list")]])
 if action.startswith("reset:"):
  name=action[6:]
  if name not in LABELS:return await event.answer("مورد نامعتبر است.",alert=True)
  await SERVICE.reset(name); t,b=await detail(name); await event.edit(t,buttons=b); return await event.answer("بازنشانی شد.")
 return await event.answer("گزینه نامعتبر است.",alert=True)

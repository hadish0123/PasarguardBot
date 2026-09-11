from __future__ import annotations
from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.support import SERVICE
from app.services.logs import SERVICE as LOGS
PREFIX=b"rep:support:"
STATE={}
DASH=RepresentativeDashboardService()
LABELS={"open":"باز","in_progress":"در حال بررسی","resolved":"حل‌شده","closed":"بسته"}

def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):
   if not await authorized(event): return await event.answer("دسترسی مدیریت ندارید.",alert=True)
   await callback_handler(event)
 async def incoming(event):
  async with tenant_dispatch(tenant_id):
   if not await authorized(event): return
   await handle_input(event)
 client.add_event_handler(callback,events.CallbackQuery(func=lambda e:bool(e.data and e.data.startswith(PREFIX))))
 client.add_event_handler(incoming,events.NewMessage(incoming=True))
async def authorized(event): return bool(event.is_private and get_tenant() and await DASH.is_owner(event.sender_id))
async def render(event,status=None,offset=0):
 rows,next_page=await SERVICE.list_admin(status,12,offset); title=LABELS.get(status,"همه") if status else "همه"
 lines=[f"🆘 **تیکت‌های پشتیبانی — {title}**",""]
 buttons=[]
 if not rows: lines.append("تیکتی وجود ندارد.")
 for r in rows:
  lines.append(f"🎫 #{r['id']} | کاربر {r['telegram_user_id']} | {r['subject']} | {LABELS.get(r['status'],r['status'])}")
  buttons.append([Button.inline(f"🎫 #{r['id']}",PREFIX+f"view:{r['id']}:".encode())])
 filters=[Button.inline("همه",PREFIX+b"list:"),Button.inline("باز",PREFIX+b"list:open"),Button.inline("درحال بررسی",PREFIX+b"list:in_progress"),Button.inline("حل‌شده",PREFIX+b"list:resolved")]
 buttons.append(filters)
 nav=[]
 if offset: nav.append(Button.inline("◀️ قبلی",PREFIX+f"list:{status or ''}:{max(0,offset-12)}".encode()))
 if next_page: nav.append(Button.inline("بعدی ▶️",PREFIX+f"list:{status or ''}:{offset+12}".encode()))
 if nav: buttons.append(nav)
 buttons.append([Button.inline("🔙 داشبورد",b"rep:rep.home")])
 return await event.edit("\n".join(lines),buttons=buttons)
async def detail(event,tid):
 t=await SERVICE.get(tid)
 if not t: return await event.answer("تیکت پیدا نشد.",alert=True)
 msgs=await SERVICE.messages(tid); out=[f"🎫 **تیکت #{tid}**",f"کاربر: `{t['telegram_user_id']}`",f"موضوع: {t['subject']}",f"وضعیت: {LABELS.get(t['status'],t['status'])}",""]
 for m in msgs[-10:]: out.append(("👤" if m["sender_role"]=="user" else "🛠")+f" {m['body']}")
 buttons=[] if t['status']=="closed" else [[Button.inline("💬 پاسخ",PREFIX+f"reply:{tid}".encode())],[Button.inline("🔄 باز",PREFIX+f"status:{tid}:open".encode()),Button.inline("⏳ بررسی",PREFIX+f"status:{tid}:in_progress".encode())],[Button.inline("✅ حل‌شده",PREFIX+f"status:{tid}:resolved".encode()),Button.inline("🔒 بستن",PREFIX+f"status:{tid}:closed".encode())]]
 buttons.append([Button.inline("🔙 لیست",PREFIX+b"list:")])
 return await event.edit("\n".join(out),buttons=buttons)
async def callback_handler(event):
 raw=event.data[len(PREFIX):].decode(errors="ignore")
 if raw.startswith("list"):
  parts=raw.split(":"); status=parts[1] if len(parts)>1 and parts[1] else None; offset=int(parts[2]) if len(parts)>2 and parts[2].isdigit() else 0; return await render(event,status,offset)
 if raw.startswith("view:"):
  try: return await detail(event,int(raw.split(":")[1]))
  except ValueError: return await event.answer("شناسه نامعتبر است.",alert=True)
 if raw.startswith("reply:"):
  try: tid=int(raw.split(":")[1])
  except ValueError: return await event.answer("شناسه نامعتبر است.",alert=True)
  if not await SERVICE.get(tid): return await event.answer("تیکت پیدا نشد.",alert=True)
  STATE[event.sender_id]={"step":"reply","ticket_id":tid}; return await event.edit("💬 متن پاسخ را ارسال کنید.\nلغو: /cancel",buttons=[[Button.inline("❌ لغو",PREFIX+f"view:{tid}".encode())]])
 if raw.startswith("status:"):
  parts=raw.split(":")
  if len(parts)!=3 or not parts[1].isdigit(): return await event.answer("درخواست نامعتبر است.",alert=True)
  try: await SERVICE.set_status(int(parts[1]),parts[2]); await LOGS.add("support.ticket.status",f"ticket={parts[1]} status={parts[2]}",event.sender_id); return await detail(event,int(parts[1]))
  except Exception as exc: return await event.answer(str(exc),alert=True)
 return await event.answer("گزینه نامعتبر است.",alert=True)
async def handle_input(event):
 state=STATE.get(event.sender_id)
 if not state:return
 text=(event.raw_text or "").strip()
 if text=="/cancel": STATE.pop(event.sender_id,None); return await event.respond("عملیات لغو شد.")
 try:
  tid=state["ticket_id"]; await SERVICE.add_message(tid,event.sender_id,"admin",text); STATE.pop(event.sender_id,None); await LOGS.add("support.ticket.reply",f"ticket={tid}",event.sender_id)
  try: await event.client.send_message((await SERVICE.get(tid))["telegram_user_id"],f"🛠 پاسخ پشتیبانی برای تیکت #{tid}:\n\n{text}")
  except Exception: pass
  return await event.respond("✅ پاسخ ثبت شد.")
 except Exception as exc:return await event.respond(f"❌ {exc}")

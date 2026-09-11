from __future__ import annotations
from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
from app.services.support import SERVICE
from app.services.logs import SERVICE as LOGS
PREFIX=b"user:support:"
STATE={}
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):
   if not await allowed(event): return await event.answer("دسترسی به این بخش را ندارید.",alert=True)
   await render_callback(event)
 async def incoming(event):
  async with tenant_dispatch(tenant_id):
   if await allowed(event): await handle_input(event)
 client.add_event_handler(callback,events.CallbackQuery(func=lambda e:bool(e.data and e.data.startswith(PREFIX))))
 client.add_event_handler(incoming,events.NewMessage(incoming=True))
async def allowed(event):
 if not event.is_private or not get_tenant(): return False
 u=await USERS.get_by_telegram_id(event.sender_id); return bool(u and not u.blocked)
def _buttons(rows):
 return [[Button.inline(f"🎫 #{r['id']} | {r['subject'][:28]}",PREFIX+f"view:{r['id']}".encode())] for r in rows]
async def render(event,user_id=None):
 uid=user_id or event.sender_id; rows=await SERVICE.list_user(uid); labels={"open":"باز","in_progress":"در حال بررسی","resolved":"حل‌شده","closed":"بسته"}
 lines=["🆘 **پشتیبانی**","","تیکت‌های شما:"]+(["هنوز تیکتی ثبت نکرده‌اید."] if not rows else [f"#{r['id']} — {r['subject']} — {labels.get(r['status'],r['status'])}" for r in rows[:8]])
 buttons=_buttons(rows[:8])+[[Button.inline("➕ ثبت تیکت جدید",PREFIX+b"new")],[Button.inline("🔄 بروزرسانی",PREFIX+b"list")],[Button.inline("🔙 فروشگاه",b"user:home")]]
 return await event.edit("\n".join(lines),buttons=buttons)
async def detail(event,tid):
 t=await SERVICE.get(tid)
 if not t or t["telegram_user_id"]!=event.sender_id:return await event.answer("تیکت پیدا نشد.",alert=True)
 msgs=await SERVICE.messages(tid); labels={"open":"باز","in_progress":"در حال بررسی","resolved":"حل‌شده","closed":"بسته"}; out=[f"🎫 **تیکت #{tid}**",f"موضوع: {t['subject']}",f"وضعیت: {labels.get(t['status'],t['status'])}",""]
 for m in msgs[-8:]:out.append(("👤 شما: " if m["sender_role"]=="user" else "🛠 پشتیبانی: ")+m["body"])
 buttons=[] if t["status"]=="closed" else [[Button.inline("💬 پاسخ",PREFIX+f"reply:{tid}".encode())]]
 buttons += [[Button.inline("🔙 تیکت‌ها",PREFIX+b"list")]]; return await event.edit("\n".join(out),buttons=buttons)
async def render_callback(event):
 raw=event.data[len(PREFIX):].decode(errors="ignore")
 if raw in {"","list"}: return await render(event)
 if raw=="new": STATE[event.sender_id]={"step":"subject"}; return await event.edit("➕ **ثبت تیکت**\n\nموضوع را ارسال کنید.\nلغو: /cancel",buttons=[[Button.inline("❌ لغو",PREFIX+b"cancel")]])
 if raw.startswith("view:"):
  try:return await detail(event,int(raw.split(":",1)[1]))
  except ValueError:return await event.answer("شناسه نامعتبر است.",alert=True)
 if raw.startswith("reply:"):
  try:tid=int(raw.split(":",1)[1])
  except ValueError:return await event.answer("شناسه نامعتبر است.",alert=True)
  t=await SERVICE.get(tid)
  if not t or t["telegram_user_id"]!=event.sender_id:return await event.answer("تیکت پیدا نشد.",alert=True)
  if t["status"]=="closed":return await event.answer("تیکت بسته شده است.",alert=True)
  STATE[event.sender_id]={"step":"reply","ticket_id":tid}; return await event.edit("💬 پاسخ خود را ارسال کنید.\nلغو: /cancel",buttons=[[Button.inline("❌ لغو",PREFIX+b"cancel")]])
 if raw=="cancel":STATE.pop(event.sender_id,None);return await render(event)
 return await event.answer("گزینه نامعتبر است.",alert=True)
async def handle_input(event):
 state=STATE.get(event.sender_id)
 if not state:return
 text=(event.raw_text or "").strip()
 if text=="/cancel":STATE.pop(event.sender_id,None);return await event.respond("عملیات لغو شد.")
 try:
  if state["step"]=="subject":
   if len(text)<2 or len(text)>160:return await event.respond("موضوع باید بین ۲ تا ۱۶۰ کاراکتر باشد.")
   state.update(step="message",subject=text);return await event.respond("حالا متن کامل مشکل را ارسال کنید.")
  if state["step"]=="message":
   ticket=await SERVICE.create_ticket(event.sender_id,state["subject"],text);STATE.pop(event.sender_id,None);await LOGS.add("support.ticket.open",f"ticket={ticket['id']}",event.sender_id);return await event.respond(f"✅ تیکت #{ticket['id']} ثبت شد.")
  if state["step"]=="reply":
   tid=state["ticket_id"];await SERVICE.add_message(tid,event.sender_id,"user",text);STATE.pop(event.sender_id,None);await LOGS.add("support.ticket.reply",f"ticket={tid}",event.sender_id);return await event.respond("✅ پاسخ شما ثبت شد.")
 except Exception as exc:return await event.respond(f"❌ {exc}")

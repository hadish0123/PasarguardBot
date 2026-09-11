from __future__ import annotations
from telethon import Button, events
from app.core.ids import USER_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
from app.services.user_wallet import SERVICE
PREFIX=b"user:wallet:"
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):
   if not await allowed(event): return await event.answer("دسترسی به این بخش ندارید.",alert=True)
   await event.answer(); await render_callback(event)
 client.add_event_handler(callback,events.CallbackQuery(func=lambda e:bool(e.data and e.data.startswith(PREFIX))))
async def allowed(event):
 if not event.is_private or not get_tenant():return False
 user=await USERS.get_by_telegram_id(event.sender_id);return bool(user and not user.blocked)
def _amount(v:float)->str:return f"{('+' if v>0 else '')}{v:,.2f}"
async def render_wallet(uid:int):
 balance=await SERVICE.balance(uid);transactions=await SERVICE.transactions(uid,5)
 text=f"💳 **کیف پول من**\n\n💰 موجودی: **{balance:,.2f}**\n"
 text+="\n🧾 آخرین تراکنش‌ها:\n"+"\n".join(f"• {_amount(float(t.amount))} — {t.reason}" for t in transactions) if transactions else "\n🧾 هنوز تراکنشی ثبت نشده است."
 return text,[[Button.inline("🧾 تاریخچه کامل",PREFIX+b"history")],[Button.inline("🔄 بروزرسانی",PREFIX+b"show")],[Button.inline("🔙 فروشگاه",b"user:"+USER_HOME.encode())]]
async def render_callback(event):
 action=event.data[len(PREFIX):].decode(errors="ignore")
 if action in ("","show"):
  t,b=await render_wallet(event.sender_id);await event.edit(t,buttons=b);return
 if action=="history":
  tx=await SERVICE.transactions(event.sender_id,50);text="🧾 **تاریخچه کیف پول**\n\n"+("\n".join(f"• {_amount(float(t.amount))} — {t.reason}" for t in tx) if tx else "هنوز تراکنشی ثبت نشده است.")
  await event.edit(text,buttons=[[Button.inline("🔙 کیف پول",PREFIX+b"show")]]);return
 await event.answer("گزینه نامعتبر است.",alert=True)

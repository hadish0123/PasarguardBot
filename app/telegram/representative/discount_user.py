from __future__ import annotations
from telethon import Button, events
from app.core.ids import USER_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.discounts import SERVICE
from app.services.representative_users import SERVICE as USERS
PREFIX=b"user:discount:"
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):
   if not await allowed(event): return await event.answer("دسترسی به این بخش را ندارید.",alert=True)
   await event.answer(); await render_callback(event)
 async def message(event):
  async with tenant_dispatch(tenant_id): await handle_message(event)
 client.add_event_handler(callback,events.CallbackQuery(data=PREFIX))
 client.add_event_handler(message,events.NewMessage(incoming=True))
async def allowed(event):
 if not event.is_private or not get_tenant(): return False
 user=await USERS.get_by_telegram_id(event.sender_id);return bool(user and not user.blocked)
async def render(event):
 await event.edit("🎟 **کد تخفیف**\n\nکد تخفیف خود را ارسال کنید تا اعتبار آن بررسی شود.\n\nبرای لغو `/cancel` را ارسال کنید.",buttons=[[Button.inline("🔙 فروشگاه",b"user:"+USER_HOME.encode())]])
 state=getattr(event.client,"_discount_users",set());event.client._discount_users=state;state.add(event.sender_id)
async def render_callback(event):
 action=event.data[len(PREFIX):].decode(errors="ignore")
 if action in ("","enter"):return await render(event)
 await event.answer("گزینه نامعتبر است.",alert=True)
async def handle_message(event):
 if not event.is_private or not get_tenant():return
 state=getattr(event.client,"_discount_users",set())
 if event.sender_id not in state:return
 user=await USERS.get_by_telegram_id(event.sender_id)
 if not user or user.blocked:return
 text=(event.raw_text or "").strip()
 if text=="/cancel":
  state.discard(event.sender_id);from app.telegram.representative.user import customer_menu
  return await event.respond("عملیات لغو شد.",buttons=await customer_menu())
 if not text or text.startswith("/"):return
 try:item=await SERVICE.validate(text)
 except (LookupError,ValueError) as exc:return await event.respond(f"❌ {exc}\n\nکد دیگری ارسال کنید یا `/cancel` بزنید.")
 state.discard(event.sender_id)
 await event.respond(f"✅ **کد معتبر است**\n\n🎟 کد: `{item.code}`\n🔥 تخفیف: **{item.percent:g}%**\n\nاین کد در مرحله پرداخت روی مبلغ سفارش اعمال خواهد شد.",buttons=[[Button.inline("🛒 خرید سرویس",b"user:buy")],[Button.inline("🔙 فروشگاه",b"user:home")]])

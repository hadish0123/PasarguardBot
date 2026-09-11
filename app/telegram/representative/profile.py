from __future__ import annotations
from telethon import Button,events
from app.core.ids import USER_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
from app.services.user_profile import SERVICE
PREFIX=b"user:profile:"
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):
   if not await allowed(event):return await event.answer("دسترسی به این بخش ندارید.",alert=True)
   await render_callback(event)
 async def message(event):
  async with tenant_dispatch(tenant_id):await handle_message(event)
 client.add_event_handler(callback,events.CallbackQuery(func=lambda e:bool(e.data and e.data.startswith(PREFIX))))
 client.add_event_handler(message,events.NewMessage(incoming=True))
async def allowed(event):
 if not event.is_private or not get_tenant():return False
 user=await USERS.get_by_telegram_id(event.sender_id);return bool(user and not user.blocked)
async def render_profile(uid:int):
 user=await SERVICE.get(uid)
 if user is None:return "👤 **پروفایل من**\n\nاطلاعات کاربری پیدا نشد.",[[Button.inline("🔙 فروشگاه",b"user:"+USER_HOME.encode())]]
 username=f"@{user.username}" if user.username else "ندارد";name=" ".join(x for x in (user.first_name,user.last_name) if x) or "ثبت نشده"
 text="👤 **پروفایل من**\n\n"+f"🆔 شناسه تلگرام: `{user.telegram_user_id}`\n👤 نام: **{name}**\n🔹 نام کاربری: **{username}**\n💰 موجودی: **{user.balance:,.2f}**"
 return text,[[Button.inline("✏️ ویرایش نام",PREFIX+b"edit_name")],[Button.inline("🔄 بروزرسانی",PREFIX+b"show")],[Button.inline("🔙 فروشگاه",b"user:"+USER_HOME.encode())]]
async def render_callback(event):
 action=event.data[len(PREFIX):].decode(errors="ignore")
 if action in ("","show"):
  t,b=await render_profile(event.sender_id);await event.edit(t,buttons=b);return await event.answer()
 if action=="edit_name":
  state=getattr(event.client,"_profile_edit_users",set());event.client._profile_edit_users=state;state.add(event.sender_id)
  await event.edit("✏️ **ویرایش نام**\n\nنام جدید را ارسال کنید:\n`نام` یا `نام|نام خانوادگی`\n\nبرای لغو `/cancel` را بفرستید.",buttons=[[Button.inline("🔙 انصراف",PREFIX+b"show")]]);return await event.answer()
 await event.answer("گزینه نامعتبر است.",alert=True)
async def handle_message(event):
 if not event.is_private or not get_tenant():return
 user=await USERS.get_by_telegram_id(event.sender_id)
 if not user or user.blocked:return
 text=(event.raw_text or "").strip();state=getattr(event.client,"_profile_edit_users",set())
 if text=="/cancel":
  state.discard(event.sender_id);from app.telegram.representative.navigation import customer_menu
  return await event.respond("عملیات لغو شد.",buttons=await customer_menu())
 if event.sender_id not in state or not text or text.startswith("/"):return
 parts=[p.strip() for p in text.split("|",1)]
 try:await SERVICE.update_name(event.sender_id,parts[0],parts[1] if len(parts)==2 else None)
 except ValueError:return await event.respond("❌ نام واردشده معتبر نیست. دوباره ارسال کنید یا `/cancel` بزنید.")
 state.discard(event.sender_id);from app.telegram.representative.navigation import customer_menu
 await event.respond("✅ نام پروفایل با موفقیت ذخیره شد.",buttons=await customer_menu())

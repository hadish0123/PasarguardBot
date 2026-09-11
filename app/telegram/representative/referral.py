from __future__ import annotations
from telethon import Button,events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
from app.services.referrals import SERVICE
PREFIX=b"user:referral"
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):
   if not await allowed(event):return await event.answer("دسترسی به این بخش را ندارید.",alert=True)
   await render_callback(event)
 client.add_event_handler(callback,events.CallbackQuery(func=lambda e:bool(e.data and e.data.startswith(PREFIX))))
async def allowed(event):
 if not event.is_private or not get_tenant():return False
 user=await USERS.get_by_telegram_id(event.sender_id);return bool(user and not user.blocked)
async def render(event):
 code=f"R{event.sender_id}";count=await SERVICE.stats(event.sender_id)
 me=await event.client.get_me();username=getattr(me,"username",None)
 buttons=[]
 if username:buttons.append([Button.url("📨 اشتراک‌گذاری لینک دعوت",f"https://t.me/{username}?start=ref_{event.sender_id}")])
 buttons += [[Button.inline("🔄 بروزرسانی",PREFIX+b":refresh")],[Button.inline("🔙 فروشگاه",b"user:home")]]
 text="👥 **دعوت دوستان**\n\n"+f"کد دعوت شما: `{code}`\n\n👤 تعداد دعوت‌های ثبت‌شده: **{count}**"
 if username:text+=f"\n\n🔗 لینک دعوت آماده است؛ با آن کاربر جدید مستقیماً به ربات شما وارد می‌شود."
 else:text+="\n\n⚠️ نام کاربری عمومی ربات تنظیم نشده است."
 return await event.edit(text,buttons=buttons)
async def render_callback(event):
 action=event.data[len(PREFIX):].decode(errors="ignore").lstrip(":")
 if action in ("","refresh"):return await render(event)
 await event.answer("گزینه نامعتبر است.",alert=True)

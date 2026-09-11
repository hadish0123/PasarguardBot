from __future__ import annotations
from telethon import Button,events
from app.core.ids import USER_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
from app.services.trial import SERVICE
PREFIX=b"user:trial"
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):
   if not await allowed(event):return await event.answer("دسترسی به این بخش را ندارید.",alert=True)
   await render_callback(event)
 client.add_event_handler(callback,events.CallbackQuery(func=lambda e:bool(e.data and e.data.startswith(PREFIX))))
async def allowed(event):
 if not event.is_private or not get_tenant():return False
 user=await USERS.get_by_telegram_id(event.sender_id);return bool(user and not user.blocked)
async def render_callback(event):
 action=event.data[len(PREFIX):].decode(errors="ignore").lstrip(":")
 if action in ("","claim"):
  try:plan=await SERVICE.claim(event.sender_id)
  except (ValueError,LookupError) as exc:return await event.edit(f"🎁 **سرویس آزمایشی**\n\n❌ {exc}",buttons=[[Button.inline("🔙 فروشگاه",b"user:"+USER_HOME.encode())]])
  return await event.edit(f"🎁 **درخواست سرویس آزمایشی ثبت شد**\n\n📦 پلن: **{plan.name}**\n💾 حجم: **{plan.volume_gb:g} GB**\n📅 مدت: **{plan.days} روز**\n\n⏳ فعال‌سازی سرویس در مرحله تحویل Pasarguard انجام می‌شود.",buttons=[[Button.inline("📦 سرویس‌های من",b"user:services")],[Button.inline("🏪 فروشگاه",b"user:home")]])
 await event.answer("گزینه نامعتبر است.",alert=True)

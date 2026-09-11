from __future__ import annotations
from datetime import datetime, timezone
from telethon import Button, events
from app.core.ids import USER_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.user_services import SERVICE
from app.services.representative_users import SERVICE as USERS
PREFIX = b"user:services:"
def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await allowed(event): return await event.answer("دسترسی به این بخش را ندارید.", alert=True)
            await render_callback(event)
    client.add_event_handler(callback, events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))))
async def allowed(event):
    if not event.is_private or not get_tenant(): return False
    user=await USERS.get_by_telegram_id(event.sender_id); return bool(user and not user.blocked)
def _status(status:str)->str:
    return {"pending_provisioning":"⏳ در انتظار تحویل","provisioning":"🔄 در حال ساخت","active":"🟢 فعال","revoked":"🔴 لغوشده"}.get(status,status)
def _date(value):
    if not value:return "—"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if value.tzinfo else value.strftime("%Y-%m-%d %H:%M")
async def render_user(telegram_user_id:int):
    services=await SERVICE.subscriptions(telegram_user_id)
    if not services:return "📦 **سرویس‌های من**\n\nهنوز سرویسی برای شما ساخته نشده است.",[[Button.inline("🛍 خرید سرویس",b"user:buy")],[Button.inline("🔙 فروشگاه",b"user:"+USER_HOME.encode())]]
    active=[s for s in services if s.status=="active"]; pending=[s for s in services if s.status in {"pending_provisioning","provisioning"}]
    text="📦 **سرویس‌های من**\n\n"+f"🟢 فعال: **{len(active)}**\n⏳ در حال تحویل: **{len(pending)}**\n📋 مجموع: **{len(services)}**\n\nسرویس موردنظر را انتخاب کنید:"
    buttons=[[Button.inline(f"#{s.id} • {s.plan_name} • {_status(s.status)}",PREFIX+f"view:{s.id}".encode())] for s in services[:10]]
    buttons += [[Button.inline("🔄 بروزرسانی",PREFIX+b"list")],[Button.inline("🛍 خرید سرویس",b"user:buy")],[Button.inline("🔙 فروشگاه",b"user:"+USER_HOME.encode())]]
    return text,buttons
async def render_callback(event):
    action=event.data[len(PREFIX):].decode(errors="ignore")
    if action in ("","list"):
        t,b=await render_user(event.sender_id);await event.edit(t,buttons=b);return await event.answer()
    if action.startswith("view:"):
        try:sid=int(action.split(":",1)[1])
        except ValueError:return await event.answer("شناسه سرویس نامعتبر است.",alert=True)
        service=await SERVICE.subscription(event.sender_id,sid)
        if service is None:return await event.answer("سرویس پیدا نشد.",alert=True)
        t=f"📦 **سرویس #{service.id}**\n\n📌 پلن: **{service.plan_name}**\n💾 حجم: **{service.volume_gb:g} GB**\n📅 مدت: **{service.days} روز**\n📊 وضعیت: **{_status(service.status)}**\n🟢 شروع: **{_date(service.starts_at)}**\n⏰ انقضا: **{_date(service.expires_at)}**"
        buttons=[]
        if service.subscription_url: buttons.append([Button.url("🔗 لینک اشتراک",service.subscription_url)])
        buttons += [[Button.inline("🔄 بروزرسانی",PREFIX+f"view:{sid}".encode())],[Button.inline("🔙 سرویس‌های من",PREFIX+b"list")]]
        return await event.edit(t,buttons=buttons)
    await event.answer("گزینه نامعتبر است.",alert=True)

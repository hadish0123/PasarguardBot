from __future__ import annotations
from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
from app.services.representative_settings import SERVICE as SETTINGS
PREFIX=b"user:support"
def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await allowed(event): return await event.answer("دسترسی به این بخش را ندارید.", alert=True)
            await render_callback(event)
    client.add_event_handler(callback, events.CallbackQuery(data=PREFIX))
async def allowed(event):
    if not event.is_private or not get_tenant(): return False
    user=await USERS.get_by_telegram_id(event.sender_id)
    return bool(user and not user.blocked)
async def render(event):
    settings=await SETTINGS.snapshot()
    username=settings.get("support_username") or ""
    contact=f"@{username.lstrip('@')}" if username else "از طریق نماینده پشتیبانی پیام ارسال کنید."
    return await event.edit("🆘 **پشتیبانی**\n\n"+f"راه ارتباطی: {contact}\n\nدر صورت مشکل در خرید، پرداخت یا سرویس، شماره سفارش و توضیح مشکل را ارسال کنید.",buttons=[[Button.inline("📦 سفارش‌های من",b"user:services")],[Button.inline("🔙 فروشگاه",b"user:home")]])
async def render_callback(event):
    action=event.data[len(PREFIX):].decode(errors="ignore").lstrip(":")
    if action in ("","open"): return await render(event)
    await event.answer("گزینه نامعتبر است.",alert=True)

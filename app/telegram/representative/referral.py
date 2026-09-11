from __future__ import annotations
from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
PREFIX=b"user:referral:"
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
    tenant=get_tenant()
    code=f"R{event.sender_id}"
    return await event.edit("👥 **دعوت دوستان**\n\n"+f"کد دعوت شما: `{code}`\n\nبا معرفی دوستان، امتیاز و مزایای سیستم دعوت در مراحل بعدی به حساب شما اضافه خواهد شد.",buttons=[[Button.inline("🔄 بروزرسانی",PREFIX+b"refresh")],[Button.inline("🔙 فروشگاه",b"user:home")]])
async def render_callback(event):
    action=event.data[len(PREFIX):].decode(errors="ignore")
    if action in ("","refresh"): return await render(event)
    await event.answer("گزینه نامعتبر است.",alert=True)

from __future__ import annotations
from telethon import Button, events
from app.core.ids import REP_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.representative_settings import SERVICE

PREFIX = b"rep:settings:"
INPUTS: dict[tuple[str, int], str] = {}

def register(client, tenant_id=None):
    async def cb(event):
        async with tenant_dispatch(tenant_id):
            if not await _auth(event): return await event.answer("دسترسی مدیریت ندارید.", alert=True)
            await handle(event)
    async def msg(event):
        async with tenant_dispatch(tenant_id):
            if not await _auth(event): return
            key=(get_tenant(), event.sender_id); field=INPUTS.get(key)
            if not field: return
            value=event.raw_text.strip()
            if value == "/cancel": INPUTS.pop(key, None); t,b=await render(); return await event.respond(t,buttons=b)
            try:
                await SERVICE.set(field,value); INPUTS.pop(key,None)
                t,b=await render(); await event.respond("✅ تنظیمات ذخیره شد.",buttons=b)
            except ValueError as exc: await event.respond(f"❌ {exc}")
    client.add_event_handler(cb, events.CallbackQuery(data=PREFIX))
    client.add_event_handler(msg, events.NewMessage(incoming=True))

async def _auth(event):
    return bool(event.is_private and get_tenant() and await RepresentativeDashboardService().is_owner(event.sender_id))

async def render():
    s=await SERVICE.snapshot()
    brand=s["brand"] or "پیش‌فرض ثبت‌نام"
    support=("@"+s["support_username"]) if s["support_username"] else "تنظیم نشده"
    return (f"⚙️ **تنظیمات نماینده**\n\n🏷 برند: **{brand}**\n🆘 پشتیبانی: **{support}**\n🌍 منطقه زمانی: **{s['timezone']}**\n\nاطلاعات این صفحه فقط برای همین نماینده ذخیره می‌شود.", [[Button.inline("🏷 ویرایش برند",PREFIX+b"edit:brand")],[Button.inline("🆘 پشتیبانی",PREFIX+b"edit:support_username")],[Button.inline("🌍 منطقه زمانی",PREFIX+b"edit:timezone")],[Button.inline("📊 داشبورد",b"rep:"+REP_HOME.encode())]])

async def handle(event):
    action=event.data[len(PREFIX):].decode(errors="ignore"); key=(get_tenant(),event.sender_id)
    if action.startswith("edit:"):
        field=action[5:]
        INPUTS[key]=field
        prompts={"brand":"🏷 نام برند جدید را ارسال کنید:","support_username":"🆘 یوزرنیم پشتیبانی را ارسال کنید (مثال: support):","timezone":"🌍 منطقه زمانی را ارسال کنید (مثال: Asia/Tehran):"}
        return await event.edit(prompts.get(field,"مقدار جدید را ارسال کنید:")+"\n\nبرای لغو `/cancel`",buttons=[[Button.inline("❌ لغو",PREFIX+b"list")]])
    if action=="list": t,b=await render(); return await event.edit(t,buttons=b)
    await event.answer("گزینه نامعتبر است.",alert=True)

from __future__ import annotations
from telethon import Button,events
from app.core.ids import REP_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.panel_status import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService
PREFIX=b"rep:panel:"
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):
   if not await _authorized(event):return await event.answer("دسترسی مدیریت ندارید.",alert=True)
   await handle(event)
 client.add_event_handler(callback,events.CallbackQuery(func=lambda e: bool(e.data and (e.data.startswith(PREFIX) or e.data==b"rep:panel"))))
async def _authorized(event):return bool(event.is_private and get_tenant() and await RepresentativeDashboardService().is_owner(event.sender_id))
async def render(status=None):
 if status is None:status=await SERVICE.snapshot()
 icons={"connected":"🟢 متصل","unreachable":"🔴 قطع / غیرقابل دسترس","unauthorized":"🟠 احراز هویت ناموفق","missing":"⚪ پیکربندی ناقص","unknown":"⚪ تست نشده"};state=icons.get(status.state,"⚠️ خطا");url=status.panel_url or "ثبت نشده";username=status.panel_username or "ثبت نشده";text=("🔌 **وضعیت اتصال پنل پاسارگواد**\n\n" f"📡 وضعیت اتصال: **{state}**\n" f"🌐 آدرس پنل: `{url}`\n" f"👤 کاربر پنل: `{username}`\n" f"🏷 وضعیت نماینده: **{status.tenant_status}**\n\n" f"ℹ️ {status.message}\n\n🔐 کلید API به‌صورت امن ذخیره شده و در این صفحه نمایش داده نمی‌شود.");buttons=[[Button.inline("🔄 تست اتصال",PREFIX+b"check")],[Button.inline("📋 نمایش دوباره",PREFIX+b"list")],[Button.inline("📊 داشبورد",b"rep:"+REP_HOME.encode())]];return text,buttons
async def handle(event):
 action=event.data[len(PREFIX):].decode(errors="ignore") if event.data.startswith(PREFIX) else "list"
 if action=="check":
  await event.edit("⏳ در حال بررسی اتصال به پنل پاسارگارد...",buttons=[]);status=await SERVICE.check();text,buttons=await render(status);await event.edit(text,buttons=buttons);return await event.answer("اتصال برقرار است." if status.state=="connected" else "نتیجه تست اتصال نمایش داده شد.")
 if action in ("list",""):text,buttons=await render();return await event.edit(text,buttons=buttons)
 return await event.answer("گزینه نامعتبر است.",alert=True)

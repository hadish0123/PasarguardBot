from __future__ import annotations
from telethon import Button,events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.orders import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService
PREFIX=b"rep:orders:";ENTRY=b"rep:rep.orders";BACK=b"rep:rep.home";DASHBOARD=RepresentativeDashboardService()
STATUS_LABELS={"pending":"🟡 در انتظار پرداخت","paid":"🔵 پرداخت‌شده","fulfilled":"🟢 تکمیل‌شده","cancelled":"🔴 لغوشده"}
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id):await callback_handler(event)
 client.add_event_handler(callback,events.CallbackQuery(func=lambda e: bool(e.data and (e.data.startswith(PREFIX) or e.data==ENTRY))))
def _status(v):return STATUS_LABELS.get(v,v)
async def _detail(order):
 r=await SERVICE.checkout_record(order.id)
 text=f"🛒 **سفارش #{order.id}**\n\n👤 کاربر: `{order.telegram_user_id}`\n📦 پلن: **{order.plan_name}**\n💾 حجم: `{order.volume_gb:g} GB`\n⏱ مدت: `{order.days}` روز\n💰 مبلغ نهایی: **{order.amount:,.2f}**\n📌 وضعیت: **{_status(order.status)}**"
 if r:text+=f"\n\n🧾 مبلغ پایه: **{r.subtotal:,.2f}**\n➖ تخفیف: **{r.discount_amount:,.2f}**\n🎟 کد: **{r.discount_code or '-'}**\n💳 شناسه پرداخت: **{r.payment_reference or 'ثبت نشده'}**"
 return text
async def render():
 orders=await SERVICE.list()
 if not orders:return "🛒 **فروش و سفارش‌ها**\n\nهنوز سفارشی ثبت نشده است.",[[Button.inline("🔙 داشبورد",BACK)]]
 lines=["🛒 **فروش و سفارش‌ها**",""];buttons=[]
 for o in orders:lines.append(f"#{o.id} — {o.plan_name} — {o.amount:,.2f} — {_status(o.status)}");buttons.append([Button.inline(f"#{o.id} | {_status(o.status)}",PREFIX+f"view:{o.id}".encode())])
 buttons.append([Button.inline("🔙 داشبورد",BACK)]);return "\n".join(lines),buttons
async def _authorized(event):return bool(event.is_private and get_tenant() and await DASHBOARD.is_owner(event.sender_id))
async def callback_handler(event):
 if not await _authorized(event):return await event.answer("دسترسی مدیریت ندارید.",alert=True)
 if event.data==ENTRY:
  t,b=await render();await event.edit(t,buttons=b);return await event.answer()
 a=event.data[len(PREFIX):].decode(errors="ignore")
 if a in {"","list"}:
  t,b=await render();await event.edit(t,buttons=b);return await event.answer()
 if a.startswith("view:"):
  o=await SERVICE.get(int(a.split(":",1)[1]))
  if o is None:return await event.answer("سفارش پیدا نشد.",alert=True)
  rows=[]
  if o.status=="pending":rows += [[Button.inline("💳 تأیید پرداخت",PREFIX+f"status:{o.id}:paid".encode())],[Button.inline("❌ لغو سفارش",PREFIX+f"status:{o.id}:cancelled".encode())]]
  elif o.status=="paid":rows += [[Button.inline("📦 تکمیل سفارش",PREFIX+f"status:{o.id}:fulfilled".encode())],[Button.inline("❌ لغو سفارش",PREFIX+f"status:{o.id}:cancelled".encode())]]
  rows += [[Button.inline("🛒 لیست سفارش‌ها",PREFIX+b"list")],[Button.inline("📊 داشبورد",BACK)]]
  await event.edit(await _detail(o),buttons=rows);return await event.answer()
 if a.startswith("status:"):
  _,oid,status=a.split(":")
  try:o=await SERVICE.set_status(int(oid),status)
  except (LookupError,ValueError) as exc:return await event.answer(str(exc),alert=True)
  await event.edit((await _detail(o))+"\n\n✅ وضعیت سفارش تغییر کرد.",buttons=[[Button.inline("🛒 سفارش‌ها",PREFIX+b"list")]]);return await event.answer()
 await event.answer("گزینه نامعتبر است.",alert=True)

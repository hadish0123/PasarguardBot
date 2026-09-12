from __future__ import annotations
from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.orders import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.subscriptions import SERVICE as SUBSCRIPTIONS
PREFIX=b"rep:orders:"; ENTRY=b"rep:rep.orders"; BACK=b"rep:rep.home"; DASHBOARD=RepresentativeDashboardService()
STATUS_LABELS={"pending":"🟡 در انتظار پرداخت","paid":"🔵 پرداخت‌شده","fulfilled":"🟢 تکمیل‌شده","cancelled":"🔴 لغوشده"}; FILTER_LABELS={"all":"همه","pending":"در انتظار","paid":"پرداخت‌شده","fulfilled":"تکمیل‌شده","cancelled":"لغوشده"}
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id): await callback_handler(event)
 client.add_event_handler(callback,events.CallbackQuery(func=lambda e:bool(e.data and(e.data.startswith(PREFIX)or e.data==ENTRY))))
def _money(v):return f"{round(float(v)):,.0f} تومان"
def _status(v):return STATUS_LABELS.get(v,v)
async def _detail(o):
 r=await SERVICE.checkout_record(o.id); s=await SUBSCRIPTIONS.get_by_order(o.id); text=f"🛒 **سفارش #{o.id}**\n\n👤 کاربر: `{o.telegram_user_id}`\n📦 پلن: **{o.plan_name}**\n💾 حجم: `{o.volume_gb:g} GB`\n⏱ مدت: `{o.days}` روز\n💰 مبلغ نهایی: **{_money(o.amount)}**\n📌 وضعیت سفارش: **{_status(o.status)}**"
 if r:text+=f"\n\n🧾 مبلغ پایه: **{_money(r.subtotal)}**\n➖ تخفیف: **{_money(r.discount_amount)}**\n🎟 کد: **{r.discount_code or '-'}**\n💳 شناسه پرداخت: **{r.payment_reference or 'ثبت نشده'}**"
 if s:text+=f"\n\n🔌 **سرویس پاسارگارد**\n📊 وضعیت: **{s.status}**\n🆔 شناسه: `{s.provider_service_id or '—'}`"
 return text
def _delivery_messages(s):
 base=(s.subscription_url or "").strip().rstrip("/")
 if not base:return None
 return f"🎉 **سرویس شما آماده شد!**\n\n📦 پلن: **{s.plan_name}**\n💾 حجم: **{s.volume_gb:g} GB**\n⏱ مدت: **{s.days} روز**\n\n🔗 **ساب اصلی:**\n`{base}`", "\n".join(["📡 **کانفیگ‌های سرویس**","","لینک هر فرمت جداگانه:"]+[f"• **{t}:** `{base}/{x}`" for t,x in(("Xray","xray"),("Clash Meta","clash_meta"),("Clash","clash"),("Sing-box","sing_box"),("WireGuard","wireguard"),("Outline","outline"))])
async def _send_delivery(e,uid,s):
 m=_delivery_messages(s)
 if not m:return
 try:await e.client.send_message(uid,m[0]);await e.client.send_message(uid,m[1])
 except Exception:pass
async def render(status="all"):
 os=await SERVICE.list(None if status=="all" else status,limit=30); title=FILTER_LABELS.get(status,"همه"); text=f"🛒 **فروش و سفارش‌ها**\n\nفیلتر: **{title}**\n\n"+(("سفارشی در این بخش وجود ندارد.") if not os else "\n".join(f"#{o.id} — {o.plan_name} — {_money(o.amount)} — {_status(o.status)}" for o in os)); b=[[Button.inline("📋 همه",PREFIX+b"filter:all"),Button.inline("🟡 انتظار",PREFIX+b"filter:pending")],[Button.inline("🔵 پرداخت",PREFIX+b"filter:paid"),Button.inline("🟢 تکمیل",PREFIX+b"filter:fulfilled"),Button.inline("🔴 لغوشده",PREFIX+b"filter:cancelled")]]+[[Button.inline(f"#{o.id} | {_status(o.status)}",PREFIX+f"view:{o.id}:{status}".encode())] for o in os]+[[Button.inline("🔙 داشبورد",BACK)]];return text,b
async def _authorized(e):return bool(e.is_private and get_tenant() and await DASHBOARD.is_owner(e.sender_id))
async def callback_handler(e):
 if not await _authorized(e):return await e.answer("دسترسی مدیریت ندارید.",alert=True)
 if e.data==ENTRY:a="list"
 else:a=e.data[len(PREFIX):].decode(errors="ignore")
 if a in {"","list"}:t,b=await render();await e.edit(t,buttons=b);return await e.answer()
 if a.startswith("filter:"):
  st=a.split(":",1)[1]
  if st not in FILTER_LABELS:return await e.answer("فیلتر نامعتبر است.",alert=True)
  t,b=await render(st);await e.edit(t,buttons=b);return await e.answer()
 if a.startswith("view:"):
  p=a.split(":");
  try:oid=int(p[1])
  except:return await e.answer("شناسه سفارش نامعتبر است.",alert=True)
  prev=p[2] if len(p)>2 and p[2] in FILTER_LABELS else "all";o=await SERVICE.get(oid)
  if not o:return await e.answer("سفارش پیدا نشد.",alert=True)
  s=await SUBSCRIPTIONS.get_by_order(oid); rows=[]
  if o.status=="pending":rows += [[Button.inline("💳 تأیید پرداخت",PREFIX+f"status:{oid}:paid:{prev}".encode())],[Button.inline("❌ لغو سفارش",PREFIX+f"status:{oid}:cancelled:{prev}".encode())]]
  elif o.status=="paid":rows += [[Button.inline("🔌 تحویل / تلاش مجدد",PREFIX+f"provision:{oid}:{prev}".encode())]] if not s or s.status!="active" else [[Button.inline("📦 ثبت تکمیل سفارش",PREFIX+f"status:{oid}:fulfilled:{prev}".encode())]];rows += [[Button.inline("❌ لغو سفارش",PREFIX+f"status:{oid}:cancelled:{prev}".encode())]]
  rows += [[Button.inline("🛒 لیست سفارش‌ها",PREFIX+f"filter:{prev}".encode())],[Button.inline("📊 داشبورد",BACK)]];await e.edit(await _detail(o),buttons=rows);return await e.answer()
 if a.startswith("provision:"):
  p=a.split(":");
  try:oid=int(p[1])
  except:return await e.answer("شناسه سفارش نامعتبر است.",alert=True)
  prev=p[2] if len(p)>2 and p[2] in FILTER_LABELS else "all";o=await SERVICE.get(oid)
  try:
   from app.services.pasarguard_provisioning import PasarguardProvisioningService
   s=await PasarguardProvisioningService().provision_paid_order(oid)
  except Exception as x:return await e.answer(f"تحویل ناموفق: {str(x)[:180]}",alert=True)
  if s.status=="active":await _send_delivery(e,o.telegram_user_id,s)
  await e.answer("✅ فرآیند تحویل اجرا شد.");return await e.edit(await _detail(o),buttons=[[Button.inline("🛒 جزئیات سفارش",PREFIX+f"view:{oid}:{prev}".encode())],[Button.inline("📋 لیست",PREFIX+f"filter:{prev}".encode())]])
 if a.startswith("status:"):
  p=a.split(":");
  try:oid=int(p[1]);st=p[2]
  except:return await e.answer("اطلاعات وضعیت نامعتبر است.",alert=True)
  prev=p[3] if len(p)>3 and p[3] in FILTER_LABELS else "all"
  try:o=await SERVICE.set_status(oid,st)
  except (LookupError,ValueError) as x:return await e.answer(str(x),alert=True)
  if st=="paid":
   if o.plan_id==0:
    try:await e.client.send_message(o.telegram_user_id,f"✅ **شارژ کیف پول تأیید شد**\n\n💰 مبلغ افزوده‌شده: **{_money(o.amount)}**\n🧾 سفارش: #{o.id}\n\nموجودی کیف پول شما افزایش یافت و اکنون می‌توانید از آن برای خرید سرویس استفاده کنید.")
    except Exception:pass
   else:
    s=await SUBSCRIPTIONS.get_by_order(oid)
    if s and s.status=="active":await _send_delivery(e,o.telegram_user_id,s)
  elif st=="cancelled":
   try:await e.client.send_message(o.telegram_user_id,f"❌ سفارش **#{o.id}** لغو شد.\n\nاگر فکر می‌کنید اشتباهی رخ داده، با پشتیبانی تماس بگیرید.")
   except Exception:pass
  await e.edit((await _detail(o))+"\n\n✅ وضعیت سفارش بروزرسانی شد.",buttons=[[Button.inline("🛒 جزئیات سفارش",PREFIX+f"view:{oid}:{prev}".encode())],[Button.inline("📋 لیست",PREFIX+f"filter:{prev}".encode())]]);return await e.answer()
 await e.answer("گزینه نامعتبر است.",alert=True)

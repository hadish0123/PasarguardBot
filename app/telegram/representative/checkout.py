from __future__ import annotations
from telethon import Button,events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.orders import SERVICE as ORDER_SERVICE
from app.services.plans import PlanService
from app.services.representative_users import SERVICE as USER_SERVICE
from app.services.sales_settings import SERVICE as SALES_SERVICE
from app.services.discounts import SERVICE as DISCOUNT_SERVICE
PREFIX=b"user:order:"; STATE={}
def key(t,u):return (t,int(u))
async def allowed(event):
 if not event.is_private or not get_tenant():return False
 u=await USER_SERVICE.get_by_telegram_id(event.sender_id);return bool(u and not u.blocked)
async def render(event,plan_id):
 plan=next((p for p in await PlanService().list() if p.id==plan_id and p.enabled),None)
 if not plan:return await event.answer("این پلن دیگر فعال نیست.",alert=True)
 s=STATE.setdefault(key(get_tenant(),event.sender_id),{});code=s.get("code");subtotal=float(plan.price);discount=0
 if code:
  try:_,discount,total=await DISCOUNT_SERVICE.calculate(code,subtotal)
  except Exception as exc:s.pop("code",None);return await event.answer(str(exc),alert=True)
 else:total=subtotal
 s["plan_id"]=plan.id;currency=(await SALES_SERVICE.snapshot()).get("currency","تومان")
 text=f"🧾 **تأیید خرید**\n\n📦 **{plan.name}**\n💾 {plan.volume_gb:g} GB · {plan.days} روز\n💰 مبلغ پایه: **{subtotal:,.2f} {currency}**"
 if code:text+=f"\n🎟 {code} · ➖ **{discount:,.2f} {currency}**"
 text+=f"\n\n💳 مبلغ نهایی: **{total:,.2f} {currency}**"
 await event.edit(text,buttons=[[Button.inline("💳 پرداخت و ثبت سفارش",PREFIX+b"pay")],[Button.inline("🎟 کد تخفیف",PREFIX+b"discount"),Button.inline("🗑 حذف تخفیف",PREFIX+b"clear")],[Button.inline("🔙 پلن‌ها",b"user:buy"),Button.inline("❌ لغو",b"user:home")]])
async def callback(event,tenant_id):
 async with tenant_dispatch(tenant_id):
  if not await allowed(event):return await event.answer("دسترسی ندارید.",alert=True)
  a=event.data[len(PREFIX):].decode(errors="ignore");s=STATE.setdefault(key(tenant_id,event.sender_id),{})
  if a=="pay":
   plan_id=s.get("plan_id")
   if not plan_id:return await event.answer("ابتدا پلن را انتخاب کنید.",alert=True)
   sales=await SALES_SERVICE.snapshot()
   if not sales.get("sales_enabled",True):return await event.answer("فروش موقتاً غیرفعال است.",alert=True)
   try:o=await ORDER_SERVICE.checkout(event.sender_id,int(plan_id),s.get("code"))
   except (LookupError,ValueError) as exc:return await event.answer(str(exc),alert=True)
   STATE.pop(key(tenant_id,event.sender_id),None);currency=sales.get("currency","تومان");r=await ORDER_SERVICE.checkout_record(o.id)
   if o.amount<=0:
    await ORDER_SERVICE.set_status(o.id,"paid");return await event.edit(f"✅ **سفارش #{o.id} پرداخت شد**\n\n📦 {o.plan_name}\n💳 0 {currency}",buttons=[[Button.inline("📦 سرویس‌های من",b"user:services")],[Button.inline("🏪 فروشگاه",b"user:home")]])
   STATE[key(tenant_id,event.sender_id)]={"payment_order_id":o.id}
   return await event.edit(f"🧾 **سفارش #{o.id}**\n\n📦 {o.plan_name}\n💰 پایه: **{r.subtotal:,.2f} {currency}**\n➖ تخفیف: **{r.discount_amount:,.2f} {currency}**\n💳 نهایی: **{r.total:,.2f} {currency}**\n\nشناسه پرداخت/کد پیگیری را ارسال کنید.",buttons=[[Button.inline("🏪 فروشگاه",b"user:home")]])
  if a=="discount":s["awaiting_discount"]=True;return await event.edit("🎟 **کد تخفیف را ارسال کنید**\n\nبرای لغو `/cancel` را بفرستید.",buttons=[[Button.inline("🔙 بازگشت",PREFIX+b"back")]])
  if a=="clear":s.pop("code",None);return await render(event,int(s["plan_id"]))
  if a=="back":s.pop("awaiting_discount",None);return await render(event,int(s["plan_id"]))
async def incoming(event,tenant_id):
 async with tenant_dispatch(tenant_id):
  if not await allowed(event):return
  s=STATE.get(key(tenant_id,event.sender_id));text=(event.raw_text or "").strip()
  if not s:return
  if text.lower()=="/cancel":STATE.pop(key(tenant_id,event.sender_id),None);return
  if s.get("awaiting_discount"):
   try:item=await DISCOUNT_SERVICE.validate(text);s["code"]=item.code;s.pop("awaiting_discount",None);await event.respond(f"✅ کد **{item.code}** اعمال شد.")
   except (LookupError,ValueError) as exc:return await event.respond(f"❌ {exc}")
   return await event.respond("کد ذخیره شد؛ به صفحه تأیید برگردید.")
  if s.get("payment_order_id"):
   try:o=await ORDER_SERVICE.submit_payment(int(s["payment_order_id"]),text)
   except (LookupError,ValueError) as exc:return await event.respond(f"❌ {exc}")
   STATE.pop(key(tenant_id,event.sender_id),None);sales=await SALES_SERVICE.snapshot();currency=sales.get("currency","تومان")
   if not sales.get("require_payment_confirmation",True):await ORDER_SERVICE.set_status(o.id,"paid");status="پرداخت‌شده"
   else:status="در انتظار تأیید مدیریت"
   return await event.respond(f"✅ پرداخت سفارش **#{o.id}** ثبت شد.\n\n💳 **{o.amount:,.2f} {currency}**\n🕐 وضعیت: **{status}**",buttons=[[Button.inline("📦 سرویس‌های من",b"user:services")],[Button.inline("🏪 فروشگاه",b"user:home")]])
def register(client,tenant_id):
 async def cb(event):await callback(event,tenant_id)
 async def msg(event):await incoming(event,tenant_id)
 client.add_event_handler(cb,events.CallbackQuery(func=lambda e:bool(e.data and e.data.startswith(PREFIX))))
 client.add_event_handler(msg,events.NewMessage(incoming=True))

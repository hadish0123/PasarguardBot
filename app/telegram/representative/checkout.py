from __future__ import annotations

from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.orders import SERVICE as ORDER_SERVICE
from app.services.plans import PlanService
from app.services.representative_users import SERVICE as USER_SERVICE
from app.services.sales_settings import SERVICE as SALES_SERVICE
from app.services.discounts import SERVICE as DISCOUNT_SERVICE
from app.services.representative_settings import SERVICE as REP_SETTINGS
from app.services.representative_dashboard import RepresentativeDashboardService

PREFIX = b"user:order:"
STATE: dict[tuple[str, int], dict] = {}

def key(t, u): return (t, int(u))

async def allowed(event):
    if not event.is_private or not get_tenant(): return False
    u = await USER_SERVICE.get_by_telegram_id(event.sender_id)
    return bool(u and not u.blocked)

def _money(value: float, currency: str) -> str:
    return f"{value:,.0f} {currency}"

async def render(event, plan_id):
    sales = await SALES_SERVICE.snapshot()
    if not sales.get("sales_enabled", True): return await event.answer("فروش در حال حاضر غیرفعال است.", alert=True)
    plan = next((p for p in await PlanService().list() if p.id == plan_id and p.enabled), None)
    if not plan: return await event.answer("این پلن دیگر فعال نیست.", alert=True)
    s = STATE.setdefault(key(get_tenant(), event.sender_id), {})
    code = s.get("code"); subtotal = float(plan.price); discount = 0.0
    if code:
        try: _, discount, total = await DISCOUNT_SERVICE.calculate(code, subtotal)
        except (LookupError, ValueError) as exc:
            s.pop("code", None); return await event.answer(str(exc), alert=True)
    else: total = subtotal
    s["plan_id"] = plan.id; currency = sales.get("currency", "تومان")
    text = f"🧾 **تأیید خرید**\n\n📦 **{plan.name}**\n💾 {plan.volume_gb:g} GB · {plan.days} روز\n💰 مبلغ پایه: **{_money(subtotal, currency)}**"
    if code: text += f"\n🎟 **{code}** · ➖ **{_money(discount, currency)}**"
    text += f"\n\n💳 مبلغ نهایی: **{_money(total, currency)}**"
    await event.edit(text, buttons=[[Button.inline("💳 ادامه و دریافت شماره کارت", PREFIX+b"pay")],[Button.inline("🎟 کد تخفیف", PREFIX+b"discount"),Button.inline("🗑 حذف تخفیف", PREFIX+b"clear")],[Button.inline("🔙 پلن‌ها",b"user:buy"),Button.inline("❌ لغو",b"user:home")]])

async def _payment_screen(event, order):
    sales = await SALES_SERVICE.snapshot(); settings = await REP_SETTINGS.snapshot(); currency = sales.get("currency", "تومان")
    card = settings.get("payment_card_number", "").strip(); holder = settings.get("payment_card_holder", "").strip()
    if not card or not holder:
        return await event.edit("⚠️ **پرداخت این فروشگاه هنوز تنظیم نشده است.**\n\nمدیر فروشگاه باید شماره کارت و نام صاحب کارت را در «تنظیمات نماینده» ثبت کند.", buttons=[[Button.inline("🔙 پلن‌ها",b"user:buy")],[Button.inline("🏪 فروشگاه",b"user:home")]])
    await event.edit(f"💳 **پرداخت سفارش #{order.id}**\n\n📦 پلن: **{order.plan_name}**\n💰 مبلغ قابل پرداخت: **{_money(order.amount,currency)}**\n\n🏦 شماره کارت:\n`{card}`\n👤 به نام: **{holder}**\n\nپس از واریز، روی «پرداخت را انجام دادم» بزنید و سپس تصویر رسید یا کد پیگیری را ارسال کنید.", buttons=[[Button.inline("✅ پرداخت را انجام دادم",PREFIX+b"submitted")],[Button.inline("❌ لغو سفارش",PREFIX+b"cancel")]])

async def callback(event, tenant_id):
    async with tenant_dispatch(tenant_id):
        if not await allowed(event): return await event.answer("دسترسی ندارید.", alert=True)
        data = bytes(event.data or b""); action = data[len(PREFIX):].decode(errors="ignore").strip(); s=STATE.setdefault(key(tenant_id,event.sender_id),{})
        if action.isdigit(): await event.answer(); return await render(event,int(action))
        if action.startswith("resume:"):
            await event.answer()
            try: order_id=int(action.split(":",1)[1])
            except (IndexError,ValueError): return await event.answer("شناسه سفارش نامعتبر است.",alert=True)
            order=await ORDER_SERVICE.get(order_id)
            if order is None or order.telegram_user_id!=event.sender_id: return await event.answer("سفارش پیدا نشد.",alert=True)
            if order.status!="pending": return await event.answer("این سفارش دیگر قابل پرداخت نیست.",alert=True)
            s.clear(); s["payment_order_id"]=order.id; return await _payment_screen(event,order)
        if action=="pay":
            plan_id=s.get("plan_id")
            if not plan_id: return await event.answer("ابتدا پلن را انتخاب کنید.",alert=True)
            await event.answer("⏳ در حال ثبت سفارش...")
            sales=await SALES_SERVICE.snapshot()
            if not sales.get("sales_enabled",True): return await event.answer("فروش موقتاً غیرفعال است.",alert=True)
            try: order=await ORDER_SERVICE.checkout(event.sender_id,int(plan_id),s.get("code"))
            except (LookupError,ValueError) as exc: return await event.answer(str(exc),alert=True)
            STATE.pop(key(tenant_id,event.sender_id),None)
            if order.amount<=0:
                await ORDER_SERVICE.set_status(order.id,"paid")
                return await event.edit(f"✅ **سفارش #{order.id} پرداخت شد**\n\n📦 {order.plan_name}\n💳 0 تومان",buttons=[[Button.inline("📦 سرویس‌های من",b"user:services")],[Button.inline("🏪 فروشگاه",b"user:home")]])
            STATE[key(tenant_id,event.sender_id)]={"payment_order_id":order.id}
            return await _payment_screen(event,order)
        if action=="submitted":
            if not s.get("payment_order_id"): return await event.answer("جلسه پرداخت منقضی شده است.",alert=True)
            s["awaiting_receipt"]=True; await event.answer()
            return await event.edit("📎 **رسید پرداخت را ارسال کنید**\n\nمی‌توانید تصویر رسید یا کد پیگیری/شناسه پرداخت را همینجا ارسال کنید.\n\nبرای لغو `/cancel` را بفرستید.",buttons=[[Button.inline("❌ لغو",PREFIX+b"cancel")]])
        if action=="cancel":
            order_id=s.get("payment_order_id"); STATE.pop(key(tenant_id,event.sender_id),None)
            if order_id:
                try: await ORDER_SERVICE.set_status(int(order_id),"cancelled")
                except (LookupError,ValueError): pass
            return await event.edit("❌ سفارش لغو شد.",buttons=[[Button.inline("🏪 فروشگاه",b"user:home")]])
        if action=="discount":
            if not s.get("plan_id"): return await event.answer("ابتدا پلن را انتخاب کنید.",alert=True)
            s["awaiting_discount"]=True; return await event.edit("🎟 **کد تخفیف را ارسال کنید**\n\nبرای لغو `/cancel` بفرستید.",buttons=[[Button.inline("🔙 بازگشت",PREFIX+b"back")]])
        if action=="clear":
            if not s.get("plan_id"): return await event.answer("جلسه خرید منقضی شده است.",alert=True)
            s.pop("code",None); return await render(event,int(s["plan_id"]))
        if action=="back":
            s.pop("awaiting_discount",None); return await render(event,int(s["plan_id"])) if s.get("plan_id") else await event.answer("جلسه خرید منقضی شده است.",alert=True)
        return await event.answer("گزینه نامعتبر است.",alert=True)

async def _notify_owner(event, order, receipt_label, photo_file_id=None):
    try:
        owner_id=int((await RepresentativeDashboardService().snapshot())["owner_id"])
        caption=(f"🔔 رسید پرداخت جدید\n\n🧾 سفارش: #{order.id}\n👤 کاربر: {order.telegram_user_id}\n📦 پلن: {order.plan_name}\n💰 مبلغ: {order.amount:,.0f} تومان\n📎 {receipt_label}\n\nاز بخش «🛒 فروش و سفارش‌ها» پرداخت را تأیید یا لغو کنید.")
        if photo_file_id:
            await event.client._request("sendPhoto", {"chat_id": owner_id, "photo": photo_file_id, "caption": caption})
        else:
            await event.client.send_message(owner_id, caption)
    except Exception:
        pass

async def incoming(event, tenant_id):
    async with tenant_dispatch(tenant_id):
        if not await allowed(event): return
        state=STATE.get(key(tenant_id,event.sender_id)); text=(event.raw_text or "").strip()
        if not state: return
        if text.lower() in {"/cancel","لغو"}:
            STATE.pop(key(tenant_id,event.sender_id),None); return await event.respond("❌ عملیات لغو شد.")
        if state.get("awaiting_discount"):
            try:
                item=await DISCOUNT_SERVICE.validate(text); state["code"]=item.code; state.pop("awaiting_discount",None); plan_id=state.get("plan_id")
                if not plan_id: STATE.pop(key(tenant_id,event.sender_id),None); return await event.respond("❌ جلسه خرید منقضی شد؛ دوباره از فروشگاه شروع کنید.")
                await event.respond(f"✅ کد **{item.code}** اعمال شد."); return await render(event,int(plan_id))
            except (LookupError,ValueError) as exc: return await event.respond(f"❌ {exc}\n\nکد دیگری ارسال کنید یا `/cancel` بزنید.")
        if state.get("payment_order_id") and state.get("awaiting_receipt"):
            order_id=int(state["payment_order_id"])
            try:
                photo_payload=(getattr(event,"_message_payload",{}) or {}).get("photo") or []
                if photo_payload:
                    file_id=photo_payload[-1].get("file_id")
                    if not file_id: raise ValueError("شناسه تصویر رسید پیدا نشد.")
                    await ORDER_SERVICE.submit_payment(order_id,f"photo:{file_id}"); receipt_label="تصویر رسید"; photo_file_id=file_id
                else:
                    if not text: return await event.respond("📎 تصویر رسید یا کد پیگیری را ارسال کنید.")
                    await ORDER_SERVICE.submit_payment(order_id,text); receipt_label=text[:80]; photo_file_id=None
                order=await ORDER_SERVICE.get(order_id); await _notify_owner(event,order,receipt_label,photo_file_id)
            except (LookupError,ValueError) as exc: return await event.respond(f"❌ {exc}")
            STATE.pop(key(tenant_id,event.sender_id),None)
            return await event.respond(f"✅ رسید سفارش **#{order_id}** دریافت شد.\n\n🕐 وضعیت: **در انتظار تأیید مدیریت**\nپس از تأیید، سرویس به‌صورت خودکار از پاسارگاد ساخته می‌شود و لینک اشتراک برای شما ارسال خواهد شد.",buttons=[[Button.inline("📦 سرویس‌های من",b"user:services")],[Button.inline("🏪 فروشگاه",b"user:home")]])

def register(client,tenant_id):
    async def cb(event): await callback(event,tenant_id)
    async def msg(event): await incoming(event,tenant_id)
    client.add_event_handler(cb,events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))))
    client.add_event_handler(msg,events.NewMessage(incoming=True))

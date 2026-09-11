from __future__ import annotations

from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.orders import SERVICE as ORDER_SERVICE
from app.services.plans import PlanService
from app.services.representative_users import SERVICE as USER_SERVICE
from app.services.sales_settings import SERVICE as SALES_SERVICE
from app.services.discounts import SERVICE as DISCOUNT_SERVICE

PREFIX = b"user:order:"
STATE: dict[tuple[str, int], dict] = {}

def key(t, u): return (t, int(u))

async def allowed(event):
    if not event.is_private or not get_tenant(): return False
    u = await USER_SERVICE.get_by_telegram_id(event.sender_id)
    return bool(u and not u.blocked)

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
    text = f"🧾 **تأیید خرید**\n\n📦 **{plan.name}**\n💾 {plan.volume_gb:g} GB · {plan.days} روز\n💰 مبلغ پایه: **{subtotal:,.2f} {currency}**"
    if code: text += f"\n🎟 **{code}** · ➖ **{discount:,.2f} {currency}**"
    text += f"\n\n💳 مبلغ نهایی: **{total:,.2f} {currency}**"
    await event.edit(text, buttons=[
        [Button.inline("💳 پرداخت و ثبت سفارش", PREFIX + b"pay")],
        [Button.inline("🎟 کد تخفیف", PREFIX + b"discount"), Button.inline("🗑 حذف تخفیف", PREFIX + b"clear")],
        [Button.inline("🔙 پلن‌ها", b"user:buy"), Button.inline("❌ لغو", b"user:home")],
    ])

async def callback(event, tenant_id):
    async with tenant_dispatch(tenant_id):
        if not await allowed(event): return await event.answer("دسترسی ندارید.", alert=True)
        action = event.data[len(PREFIX):].decode(errors="ignore").strip()
        s = STATE.setdefault(key(tenant_id, event.sender_id), {})
        # Plan buttons carry the numeric plan id directly: user:order:<plan_id>.
        # This branch is the missing transition that previously produced "گزینه نامعتبر".
        if action.isdigit():
            await event.answer()
            return await render(event, int(action))
        if action.startswith("resume:"):
            await event.answer()
            try: order_id = int(action.split(":", 1)[1])
            except (IndexError, ValueError): return await event.answer("شناسه سفارش نامعتبر است.", alert=True)
            order = await ORDER_SERVICE.get(order_id)
            if order is None or order.telegram_user_id != event.sender_id: return await event.answer("سفارش پیدا نشد.", alert=True)
            if order.status != "pending": return await event.answer("این سفارش دیگر قابل پرداخت نیست.", alert=True)
            record = await ORDER_SERVICE.checkout_record(order.id)
            if record is None: return await event.answer("جزئیات پرداخت سفارش پیدا نشد.", alert=True)
            s.clear(); s["payment_order_id"] = order.id; sales = await SALES_SERVICE.snapshot(); currency = sales.get("currency", "تومان")
            await event.edit(f"🧾 **ادامه پرداخت سفارش #{order.id}**\n\n📦 {order.plan_name}\n💰 پایه: **{record.subtotal:,.2f} {currency}**\n➖ تخفیف: **{record.discount_amount:,.2f} {currency}**\n💳 نهایی: **{record.total:,.2f} {currency}**\n\nشناسه پرداخت/کد پیگیری را ارسال کنید.\n\nبرای لغو `/cancel` را بفرستید.", buttons=[[Button.inline("🏪 فروشگاه", b"user:home")]])
            return
        if action == "pay":
            plan_id = s.get("plan_id")
            if not plan_id: return await event.answer("ابتدا پلن را انتخاب کنید.", alert=True)
            await event.answer("⏳ در حال ثبت سفارش...")
            sales = await SALES_SERVICE.snapshot()
            if not sales.get("sales_enabled", True): return await event.answer("فروش موقتاً غیرفعال است.", alert=True)
            try: order = await ORDER_SERVICE.checkout(event.sender_id, int(plan_id), s.get("code"))
            except (LookupError, ValueError) as exc: return await event.answer(str(exc), alert=True)
            STATE.pop(key(tenant_id, event.sender_id), None); currency = sales.get("currency", "تومان"); record = await ORDER_SERVICE.checkout_record(order.id)
            if order.amount <= 0:
                await ORDER_SERVICE.set_status(order.id, "paid")
                return await event.edit(f"✅ **سفارش #{order.id} پرداخت شد**\n\n📦 {order.plan_name}\n💳 0 {currency}", buttons=[[Button.inline("📦 سرویس‌های من", b"user:services")], [Button.inline("🏪 فروشگاه", b"user:home")]])
            STATE[key(tenant_id, event.sender_id)] = {"payment_order_id": order.id}
            await event.edit(f"🧾 **سفارش #{order.id}**\n\n📦 {order.plan_name}\n💰 پایه: **{record.subtotal:,.2f} {currency}**\n➖ تخفیف: **{record.discount_amount:,.2f} {currency}**\n💳 نهایی: **{record.total:,.2f} {currency}**\n\nشناسه پرداخت/کد پیگیری را ارسال کنید.", buttons=[[Button.inline("🏪 فروشگاه", b"user:home")]])
            return
        if action == "discount":
            if not s.get("plan_id"): return await event.answer("ابتدا پلن را انتخاب کنید.", alert=True)
            s["awaiting_discount"] = True
            return await event.edit("🎟 **کد تخفیف را ارسال کنید**\n\nبرای لغو `/cancel` بفرستید.", buttons=[[Button.inline("🔙 بازگشت", PREFIX + b"back")]])
        if action == "clear":
            if not s.get("plan_id"): return await event.answer("جلسه خرید منقضی شده است.", alert=True)
            s.pop("code", None); return await render(event, int(s["plan_id"]))
        if action == "back":
            s.pop("awaiting_discount", None)
            return await render(event, int(s["plan_id"])) if s.get("plan_id") else await event.answer("جلسه خرید منقضی شده است.", alert=True)
        return await event.answer("گزینه نامعتبر است.", alert=True)

async def incoming(event, tenant_id):
    async with tenant_dispatch(tenant_id):
        if not await allowed(event): return
        state = STATE.get(key(tenant_id, event.sender_id)); text = (event.raw_text or "").strip()
        if not state: return
        if text.lower() in {"/cancel", "لغو"}:
            STATE.pop(key(tenant_id, event.sender_id), None); return await event.respond("❌ عملیات لغو شد.")
        if state.get("awaiting_discount"):
            try:
                item = await DISCOUNT_SERVICE.validate(text); state["code"] = item.code; state.pop("awaiting_discount", None); plan_id = state.get("plan_id")
                if not plan_id:
                    STATE.pop(key(tenant_id, event.sender_id), None); return await event.respond("❌ جلسه خرید منقضی شد؛ دوباره از فروشگاه شروع کنید.")
                await event.respond(f"✅ کد **{item.code}** اعمال شد."); return await render(event, int(plan_id))
            except (LookupError, ValueError) as exc: return await event.respond(f"❌ {exc}\n\nکد دیگری ارسال کنید یا `/cancel` بزنید.")
        if state.get("payment_order_id"):
            try: order = await ORDER_SERVICE.submit_payment(int(state["payment_order_id"]), text)
            except (LookupError, ValueError) as exc: return await event.respond(f"❌ {exc}")
            STATE.pop(key(tenant_id, event.sender_id), None); sales = await SALES_SERVICE.snapshot(); currency = sales.get("currency", "تومان")
            if not sales.get("allow_pending_orders", True):
                await ORDER_SERVICE.set_status(order.id, "cancelled"); return await event.respond("❌ ثبت سفارش معلق غیرفعال است؛ سفارش لغو شد.")
            if not sales.get("require_payment_confirmation", True):
                try: await ORDER_SERVICE.set_status(order.id, "paid"); status = "پرداخت‌شده و در حال تحویل"
                except Exception: status = "پرداخت ثبت شد؛ تحویل نیاز به بررسی مدیریت دارد"
            else: status = "در انتظار تأیید مدیریت"
            return await event.respond(f"✅ پرداخت سفارش **#{order.id}** ثبت شد.\n\n💳 **{order.amount:,.2f} {currency}**\n🕐 وضعیت: **{status}**", buttons=[[Button.inline("📦 سرویس‌های من", b"user:services")], [Button.inline("🏪 فروشگاه", b"user:home")]])

def register(client, tenant_id):
    async def cb(event): await callback(event, tenant_id)
    async def msg(event): await incoming(event, tenant_id)
    client.add_event_handler(cb, events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))))
    client.add_event_handler(msg, events.NewMessage(incoming=True))

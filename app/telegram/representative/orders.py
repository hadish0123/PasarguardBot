from __future__ import annotations

from telethon import Button, events

from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.orders import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.subscriptions import SERVICE as SUBSCRIPTIONS

PREFIX = b"rep:orders:"
ENTRY = b"rep:rep.orders"
BACK = b"rep:rep.home"
DASHBOARD = RepresentativeDashboardService()
STATUS_LABELS = {"pending": "🟡 در انتظار پرداخت", "paid": "🔵 پرداخت‌شده", "fulfilled": "🟢 تکمیل‌شده", "cancelled": "🔴 لغوشده"}
FILTER_LABELS = {"all": "همه", "pending": "در انتظار", "paid": "پرداخت‌شده", "fulfilled": "تکمیل‌شده", "cancelled": "لغوشده"}

def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id): await callback_handler(event)
    client.add_event_handler(callback, events.CallbackQuery(func=lambda e: bool(e.data and (e.data.startswith(PREFIX) or e.data == ENTRY))))

def _money(value: float) -> str: return f"{round(float(value)):,.0f} تومان"
def _status(value): return STATUS_LABELS.get(value, value)

async def _detail(order):
    record = await SERVICE.checkout_record(order.id); subscription = await SUBSCRIPTIONS.get_by_order(order.id)
    text = (f"🛒 **سفارش #{order.id}**\n\n👤 کاربر: `{order.telegram_user_id}`\n📦 پلن: **{order.plan_name}**\n💾 حجم: `{order.volume_gb:g} GB`\n⏱ مدت: `{order.days}` روز\n💰 مبلغ نهایی: **{_money(order.amount)}**\n📌 وضعیت سفارش: **{_status(order.status)}**")
    if record: text += f"\n\n🧾 مبلغ پایه: **{_money(record.subtotal)}**\n➖ تخفیف: **{_money(record.discount_amount)}**\n🎟 کد: **{record.discount_code or '-'}**\n💳 شناسه پرداخت: **{record.payment_reference or 'ثبت نشده'}**"
    if subscription:
        text += f"\n\n🔌 **سرویس پاسارگارد**\n📊 وضعیت: **{subscription.status}**\n🆔 شناسه: `{subscription.provider_service_id or '—'}`"
        if subscription.subscription_url: text += "\n🔗 لینک اشتراک: آماده"
    return text

def _delivery_messages(subscription):
    base=(subscription.subscription_url or "").strip().rstrip("/")
    if not base: return None
    sub=(f"🎉 **سرویس شما آماده شد!**\n\n📦 پلن: **{subscription.plan_name}**\n💾 حجم: **{subscription.volume_gb:g} GB**\n⏱ مدت: **{subscription.days} روز**\n\n🔗 **ساب اصلی:**\n`{base}`")
    formats=(("Xray","xray"),("Clash Meta","clash_meta"),("Clash","clash"),("Sing-box","sing_box"),("WireGuard","wireguard"),("Outline","outline"))
    return sub, "\n".join(["📡 **کانفیگ‌های سرویس**","","لینک هر فرمت جداگانه:"]+[f"• **{t}:** `{base}/{s}`" for t,s in formats])

async def _send_delivery(event,user_id,subscription):
    messages=_delivery_messages(subscription)
    if not messages:return
    try:
        await event.client.send_message(user_id,messages[0]); await event.client.send_message(user_id,messages[1])
    except Exception: pass

async def render(status="all"):
    orders=await SERVICE.list(None if status=="all" else status,limit=30); title=FILTER_LABELS.get(status,"همه")
    if not orders:text=f"🛒 **فروش و سفارش‌ها**\n\nفیلتر: **{title}**\n\nسفارشی در این بخش وجود ندارد."
    else:text="\n".join(["🛒 **فروش و سفارش‌ها**",f"فیلتر: **{title}**",""]+[f"#{o.id} — {o.plan_name} — {_money(o.amount)} — {_status(o.status)}" for o in orders])
    buttons=[[Button.inline("📋 همه",PREFIX+b"filter:all"),Button.inline("🟡 انتظار",PREFIX+b"filter:pending")],[Button.inline("🔵 پرداخت",PREFIX+b"filter:paid"),Button.inline("🟢 تکمیل",PREFIX+b"filter:fulfilled"),Button.inline("🔴 لغوشده",PREFIX+b"filter:cancelled")]]
    buttons += [[Button.inline(f"#{o.id} | {_status(o.status)}",PREFIX+f"view:{o.id}:{status}".encode())] for o in orders]
    buttons.append([Button.inline("🔙 داشبورد",BACK)]); return text,buttons

async def _authorized(event): return bool(event.is_private and get_tenant() and await DASHBOARD.is_owner(event.sender_id))

async def callback_handler(event):
    if not await _authorized(event): return await event.answer("دسترسی مدیریت ندارید.",alert=True)
    if event.data==ENTRY:
        text,buttons=await render(); await event.edit(text,buttons=buttons); return await event.answer()
    action=event.data[len(PREFIX):].decode(errors="ignore")
    if action in {"","list"}:
        text,buttons=await render(); await event.edit(text,buttons=buttons); return await event.answer()
    if action.startswith("filter:"):
        status=action.split(":",1)[1]
        if status not in FILTER_LABELS:return await event.answer("فیلتر نامعتبر است.",alert=True)
        text,buttons=await render(status); await event.edit(text,buttons=buttons); return await event.answer()
    if action.startswith("view:"):
        parts=action.split(":")
        try:order_id=int(parts[1])
        except (IndexError,ValueError):return await event.answer("شناسه سفارش نامعتبر است.",alert=True)
        prev=parts[2] if len(parts)>2 and parts[2] in FILTER_LABELS else "all"; order=await SERVICE.get(order_id)
        if order is None:return await event.answer("سفارش پیدا نشد.",alert=True)
        subscription=await SUBSCRIPTIONS.get_by_order(order.id); rows=[]
        if order.status=="pending":rows += [[Button.inline("💳 تأیید پرداخت",PREFIX+f"status:{order.id}:paid:{prev}".encode())],[Button.inline("❌ لغو سفارش",PREFIX+f"status:{order.id}:cancelled:{prev}".encode())]]
        elif order.status=="paid":
            rows += [[Button.inline("🔌 تحویل / تلاش مجدد",PREFIX+f"provision:{order.id}:{prev}".encode())]] if not subscription or subscription.status!="active" else [[Button.inline("📦 ثبت تکمیل سفارش",PREFIX+f"status:{order.id}:fulfilled:{prev}".encode())]]
            rows += [[Button.inline("❌ لغو سفارش",PREFIX+f"status:{order.id}:cancelled:{prev}".encode())]]
        rows += [[Button.inline("🛒 لیست سفارش‌ها",PREFIX+f"filter:{prev}".encode())],[Button.inline("📊 داشبورد",BACK)]]
        await event.edit(await _detail(order),buttons=rows); return await event.answer()
    if action.startswith("provision:"):
        parts=action.split(":")
        try:order_id=int(parts[1])
        except (IndexError,ValueError):return await event.answer("شناسه سفارش نامعتبر است.",alert=True)
        prev=parts[2] if len(parts)>2 and parts[2] in FILTER_LABELS else "all"; order=await SERVICE.get(order_id)
        if order is None:return await event.answer("سفارش پیدا نشد.",alert=True)
        try:
            from app.services.pasarguard_provisioning import PasarguardProvisioningService
            subscription=await PasarguardProvisioningService().provision_paid_order(order_id)
        except Exception as exc:return await event.answer(f"تحویل ناموفق: {str(exc)[:180]}",alert=True)
        if subscription.status=="active":await _send_delivery(event,order.telegram_user_id,subscription)
        await event.answer("✅ فرآیند تحویل اجرا شد."); await event.edit(await _detail(order),buttons=[[Button.inline("🛒 جزئیات سفارش",PREFIX+f"view:{order_id}:{prev}".encode())],[Button.inline("📋 لیست",PREFIX+f"filter:{prev}".encode())]]); return
    if action.startswith("status:"):
        parts=action.split(":")
        try:order_id=int(parts[1]); status=parts[2]
        except (IndexError,ValueError):return await event.answer("اطلاعات وضعیت نامعتبر است.",alert=True)
        prev=parts[3] if len(parts)>3 and parts[3] in FILTER_LABELS else "all"
        try:order=await SERVICE.set_status(order_id,status)
        except (LookupError,ValueError) as exc:return await event.answer(str(exc),alert=True)
        if status=="paid":
            subscription=await SUBSCRIPTIONS.get_by_order(order_id)
            if subscription and subscription.status=="active":await _send_delivery(event,order.telegram_user_id,subscription)
        elif status=="cancelled":
            try:await event.client.send_message(order.telegram_user_id,f"❌ سفارش **#{order.id}** لغو شد.\n\nاگر فکر می‌کنید اشتباهی رخ داده، با پشتیبانی تماس بگیرید.")
            except Exception:pass
        await event.edit((await _detail(order))+"\n\n✅ وضعیت سفارش بروزرسانی شد.",buttons=[[Button.inline("🛒 جزئیات سفارش",PREFIX+f"view:{order_id}:{prev}".encode())],[Button.inline("📋 لیست",PREFIX+f"filter:{prev}".encode())]]); return await event.answer()
    await event.answer("گزینه نامعتبر است.",alert=True)

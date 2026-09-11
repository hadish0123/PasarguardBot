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
STATUS_LABELS = {
    "pending": "🟡 در انتظار پرداخت",
    "paid": "🔵 پرداخت‌شده",
    "fulfilled": "🟢 تکمیل‌شده",
    "cancelled": "🔴 لغوشده",
}
FILTER_LABELS = {
    "all": "همه",
    "pending": "در انتظار",
    "paid": "پرداخت‌شده",
    "fulfilled": "تکمیل‌شده",
    "cancelled": "لغوشده",
}


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            await callback_handler(event)

    client.add_event_handler(
        callback,
        events.CallbackQuery(func=lambda e: bool(e.data and (e.data.startswith(PREFIX) or e.data == ENTRY))),
    )


def _status(value):
    return STATUS_LABELS.get(value, value)


async def _detail(order):
    record = await SERVICE.checkout_record(order.id)
    subscription = await SUBSCRIPTIONS.get_by_order(order.id)
    text = (
        f"🛒 **سفارش #{order.id}**\n\n"
        f"👤 کاربر: `{order.telegram_user_id}`\n"
        f"📦 پلن: **{order.plan_name}**\n"
        f"💾 حجم: `{order.volume_gb:g} GB`\n"
        f"⏱ مدت: `{order.days}` روز\n"
        f"💰 مبلغ نهایی: **{order.amount:,.2f}**\n"
        f"📌 وضعیت سفارش: **{_status(order.status)}**"
    )
    if record:
        text += (
            f"\n\n🧾 مبلغ پایه: **{record.subtotal:,.2f}**"
            f"\n➖ تخفیف: **{record.discount_amount:,.2f}**"
            f"\n🎟 کد: **{record.discount_code or '-'}**"
            f"\n💳 شناسه پرداخت: **{record.payment_reference or 'ثبت نشده'}**"
        )
    if subscription:
        text += (
            f"\n\n🔌 **سرویس پاسارگارد**"
            f"\n📊 وضعیت: **{subscription.status}**"
            f"\n🆔 شناسه: `{subscription.provider_service_id or '—'}`"
        )
        if subscription.subscription_url:
            text += "\n🔗 لینک اشتراک: آماده"
    return text


async def render(status="all"):
    orders = await SERVICE.list(None if status == "all" else status, limit=30)
    title = FILTER_LABELS.get(status, "همه")
    if not orders:
        text = f"🛒 **فروش و سفارش‌ها**\n\nفیلتر: **{title}**\n\nسفارشی در این بخش وجود ندارد."
    else:
        lines = ["🛒 **فروش و سفارش‌ها**", f"فیلتر: **{title}**", ""]
        for order in orders:
            lines.append(f"#{order.id} — {order.plan_name} — {order.amount:,.2f} — {_status(order.status)}")
        text = "\n".join(lines)
    buttons = []
    buttons.append([
        Button.inline("📋 همه", PREFIX + b"filter:all"),
        Button.inline("🟡 انتظار", PREFIX + b"filter:pending"),
    ])
    buttons.append([
        Button.inline("🔵 پرداخت", PREFIX + b"filter:paid"),
        Button.inline("🟢 تکمیل", PREFIX + b"filter:fulfilled"),
        Button.inline("🔴 لغوشده", PREFIX + b"filter:cancelled"),
    ])
    for order in orders:
        buttons.append([
            Button.inline(
                f"#{order.id} | {_status(order.status)}",
                PREFIX + f"view:{order.id}:{status}".encode(),
            )
        ])
    buttons.append([Button.inline("🔙 داشبورد", BACK)])
    return text, buttons


async def _authorized(event):
    return bool(event.is_private and get_tenant() and await DASHBOARD.is_owner(event.sender_id))


async def callback_handler(event):
    if not await _authorized(event):
        return await event.answer("دسترسی مدیریت ندارید.", alert=True)

    if event.data == ENTRY:
        text, buttons = await render()
        await event.edit(text, buttons=buttons)
        return await event.answer()

    action = event.data[len(PREFIX):].decode(errors="ignore")
    if action in {"", "list"}:
        text, buttons = await render()
        await event.edit(text, buttons=buttons)
        return await event.answer()

    if action.startswith("filter:"):
        status = action.split(":", 1)[1]
        if status not in FILTER_LABELS:
            return await event.answer("فیلتر نامعتبر است.", alert=True)
        text, buttons = await render(status)
        await event.edit(text, buttons=buttons)
        return await event.answer()

    if action.startswith("view:"):
        parts = action.split(":")
        try:
            order_id = int(parts[1])
        except (IndexError, ValueError):
            return await event.answer("شناسه سفارش نامعتبر است.", alert=True)
        previous_filter = parts[2] if len(parts) > 2 and parts[2] in FILTER_LABELS else "all"
        order = await SERVICE.get(order_id)
        if order is None:
            return await event.answer("سفارش پیدا نشد.", alert=True)
        subscription = await SUBSCRIPTIONS.get_by_order(order.id)
        rows = []
        if order.status == "pending":
            rows += [[Button.inline("💳 تأیید پرداخت", PREFIX + f"status:{order.id}:paid:{previous_filter}".encode())]]
            rows += [[Button.inline("❌ لغو سفارش", PREFIX + f"status:{order.id}:cancelled:{previous_filter}".encode())]]
        elif order.status == "paid":
            if not subscription or subscription.status != "active":
                rows += [[Button.inline("🔌 تحویل / تلاش مجدد", PREFIX + f"provision:{order.id}:{previous_filter}".encode())]]
            else:
                rows += [[Button.inline("📦 ثبت تکمیل سفارش", PREFIX + f"status:{order.id}:fulfilled:{previous_filter}".encode())]]
            rows += [[Button.inline("❌ لغو سفارش", PREFIX + f"status:{order.id}:cancelled:{previous_filter}".encode())]]
        rows += [[Button.inline("🛒 لیست سفارش‌ها", PREFIX + f"filter:{previous_filter}".encode())]]
        rows += [[Button.inline("📊 داشبورد", BACK)]]
        await event.edit(await _detail(order), buttons=rows)
        return await event.answer()

    if action.startswith("provision:"):
        parts = action.split(":")
        try:
            order_id = int(parts[1])
        except (IndexError, ValueError):
            return await event.answer("شناسه سفارش نامعتبر است.", alert=True)
        previous_filter = parts[2] if len(parts) > 2 and parts[2] in FILTER_LABELS else "all"
        order = await SERVICE.get(order_id)
        if order is None:
            return await event.answer("سفارش پیدا نشد.", alert=True)
        try:
            from app.services.pasarguard_provisioning import PasarguardProvisioningService
            subscription = await PasarguardProvisioningService().provision_paid_order(order_id)
        except Exception as exc:
            return await event.answer(f"تحویل ناموفق: {str(exc)[:180]}", alert=True)
        if subscription.status == "active":
            try:
                message = (
                    f"🎉 **سرویس شما آماده شد!**\n\n"
                    f"📦 پلن: **{subscription.plan_name}**\n"
                    f"💾 حجم: **{subscription.volume_gb:g} GB**\n"
                    f"⏱ مدت: **{subscription.days} روز**"
                )
                if subscription.subscription_url:
                    message += f"\n\n🔗 لینک اشتراک:\n{subscription.subscription_url}"
                await event.client.send_message(order.telegram_user_id, message)
            except Exception:
                pass
        await event.answer("✅ فرآیند تحویل اجرا شد.")
        rows = [[Button.inline("🛒 جزئیات سفارش", PREFIX + f"view:{order_id}:{previous_filter}".encode())], [Button.inline("📋 لیست", PREFIX + f"filter:{previous_filter}".encode())]]
        await event.edit(await _detail(order), buttons=rows)
        return

    if action.startswith("status:"):
        parts = action.split(":")
        try:
            order_id = int(parts[1])
            status = parts[2]
        except (IndexError, ValueError):
            return await event.answer("اطلاعات وضعیت نامعتبر است.", alert=True)
        previous_filter = parts[3] if len(parts) > 3 and parts[3] in FILTER_LABELS else "all"
        try:
            order = await SERVICE.set_status(order_id, status)
        except (LookupError, ValueError) as exc:
            return await event.answer(str(exc), alert=True)

        if status == "paid":
            subscription = await SUBSCRIPTIONS.get_by_order(order_id)
            if subscription and subscription.status == "active":
                try:
                    message = (
                        f"🎉 **سرویس شما آماده شد!**\n\n"
                        f"📦 پلن: **{subscription.plan_name}**\n"
                        f"💾 حجم: **{subscription.volume_gb:g} GB**\n"
                        f"⏱ مدت: **{subscription.days} روز**"
                    )
                    if subscription.subscription_url:
                        message += f"\n\n🔗 لینک اشتراک:\n{subscription.subscription_url}"
                    await event.client.send_message(order.telegram_user_id, message)
                except Exception:
                    pass
        elif status == "cancelled":
            try:
                await event.client.send_message(
                    order.telegram_user_id,
                    f"❌ سفارش **#{order.id}** لغو شد.\n\nاگر فکر می‌کنید اشتباهی رخ داده، با پشتیبانی تماس بگیرید.",
                )
            except Exception:
                pass

        rows = [[Button.inline("🛒 جزئیات سفارش", PREFIX + f"view:{order_id}:{previous_filter}".encode())], [Button.inline("📋 لیست", PREFIX + f"filter:{previous_filter}".encode())]]
        await event.edit((await _detail(order)) + "\n\n✅ وضعیت سفارش بروزرسانی شد.", buttons=rows)
        return await event.answer()

    await event.answer("گزینه نامعتبر است.", alert=True)

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from telethon import Button, events

from app.db.models import CheckoutRecord, Order, ServiceSubscription, TenantRecord
from app.db.session import SessionFactory
from app.services.central_admin import CentralAdminService
from app.services.pasarguard_provisioning import PasarguardProvisioningService


SERVICE = CentralAdminService()
PREFIX = b"central:admin:order:"
_AWAITING_TRACKING: set[int] = set()


def install_order_tracking(client) -> None:
    """Install central-admin order tracking and inject its dashboard button."""
    from app.telegram.central import admin as admin_module

    original = getattr(admin_module, "dashboard_buttons")
    if not getattr(original, "_order_tracking_wrapped", False):
        def dashboard_buttons_with_orders():
            rows = list(original())
            rows.append([Button.inline("🧾 پیگیری سفارش", PREFIX + b"input")])
            return rows
        dashboard_buttons_with_orders._order_tracking_wrapped = True
        admin_module.dashboard_buttons = dashboard_buttons_with_orders

    client.add_event_handler(order_tracking_callback, events.CallbackQuery())
    client.add_event_handler(order_tracking_text, events.NewMessage(incoming=True))
    print("[central-admin-orders] handlers registered", flush=True)


def _is_admin(event) -> bool:
    return bool(event.is_private and SERVICE.is_admin(event.sender_id))


def _money(value: float) -> str:
    return f"{float(value):,.0f} تومان"


def _dt(value) -> str:
    if value is None:
        return "—"
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


async def _find_tracking(code: str):
    if SessionFactory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    code = code.strip().upper()
    async with SessionFactory() as session:
        result = await session.execute(
            select(Order, CheckoutRecord, ServiceSubscription, TenantRecord)
            .outerjoin(CheckoutRecord, (CheckoutRecord.order_id == Order.id) & (CheckoutRecord.tenant_id == Order.tenant_id))
            .outerjoin(ServiceSubscription, (ServiceSubscription.order_id == Order.id) & (ServiceSubscription.tenant_id == Order.tenant_id))
            .join(TenantRecord, TenantRecord.id == Order.tenant_id)
            .where(Order.id == select(Order.id).where(Order.id == Order.id).scalar_subquery())
        )
        # Order does not have a tracking_code column; representative registration owns the PG code.
        from app.db.models import RepresentativeRegistration
        result = await session.execute(
            select(Order, CheckoutRecord, ServiceSubscription, TenantRecord, RepresentativeRegistration)
            .outerjoin(CheckoutRecord, (CheckoutRecord.order_id == Order.id) & (CheckoutRecord.tenant_id == Order.tenant_id))
            .outerjoin(ServiceSubscription, (ServiceSubscription.order_id == Order.id) & (ServiceSubscription.tenant_id == Order.tenant_id))
            .join(TenantRecord, TenantRecord.id == Order.tenant_id)
            .join(RepresentativeRegistration, RepresentativeRegistration.id == TenantRecord.registration_id)
            .where(RepresentativeRegistration.tracking_code == code)
            .order_by(Order.id.desc())
        )
        return result.first()


async def _get_order(order_id: int):
    if SessionFactory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with SessionFactory() as session:
        return await session.scalar(select(Order).where(Order.id == order_id))


async def _set_paid_admin(order_id: int):
    if SessionFactory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with SessionFactory() as session:
        order = await session.get(Order, order_id)
        if order is None:
            raise LookupError("سفارش پیدا نشد.")
        if order.status == "paid":
            return order
        if order.status != "pending":
            raise ValueError(f"وضعیت فعلی {order.status} قابل تأیید پرداخت نیست.")
        order.status = "paid"
        record = await session.scalar(select(CheckoutRecord).where(CheckoutRecord.order_id == order.id, CheckoutRecord.tenant_id == order.tenant_id))
        if record is not None and not record.payment_reference:
            record.payment_reference = "CENTRAL-ADMIN"
            record.payment_submitted_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(order)
        return order


async def _mark_fulfilled(order_id: int):
    if SessionFactory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with SessionFactory() as session:
        order = await session.get(Order, order_id)
        if order is None:
            raise LookupError("سفارش پیدا نشد.")
        subscription = await session.scalar(select(ServiceSubscription).where(ServiceSubscription.order_id == order.id, ServiceSubscription.tenant_id == order.tenant_id))
        if subscription is None or subscription.status != "active":
            raise ValueError("ابتدا سرویس باید در پاسارگارد فعال شود.")
        if order.status == "fulfilled":
            return order
        if order.status != "paid":
            raise ValueError("فقط سفارش پرداخت‌شده قابل تکمیل است.")
        order.status = "fulfilled"
        await session.commit()
        await session.refresh(order)
        return order


async def _cancel_order(order_id: int):
    if SessionFactory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with SessionFactory() as session:
        order = await session.get(Order, order_id)
        if order is None:
            raise LookupError("سفارش پیدا نشد.")
        subscription = await session.scalar(select(ServiceSubscription).where(ServiceSubscription.order_id == order.id, ServiceSubscription.tenant_id == order.tenant_id))
        if subscription and subscription.status == "active":
            raise ValueError("این سفارش سرویس فعال دارد؛ ابتدا سرویس را از پنل پاسارگارد لغو/ابطال کنید.")
        if order.status in {"cancelled", "fulfilled"}:
            return order
        order.status = "cancelled"
        await session.commit()
        await session.refresh(order)
        return order


def _buttons(order, subscription, tracking_code: str):
    rows = []
    if order.status == "pending":
        rows.append([Button.inline("💳 تأیید پرداخت و آماده‌سازی", PREFIX + f"paid:{order.id}".encode())])
    if order.status == "paid" and (subscription is None or subscription.status != "active"):
        rows.append([Button.inline("⚡ ساخت و فعال‌سازی سرویس", PREFIX + f"provision:{order.id}".encode())])
    if order.status == "paid" and subscription is not None and subscription.status == "active":
        rows.append([Button.inline("✅ تکمیل سفارش", PREFIX + f"fulfilled:{order.id}".encode())])
    if order.status not in {"cancelled", "fulfilled"} and not (subscription and subscription.status == "active"):
        rows.append([Button.inline("🗑 لغو سفارش", PREFIX + f"cancel:{order.id}".encode())])
    rows.append([Button.inline("🔄 بروزرسانی وضعیت", PREFIX + f"view:{order.id}".encode())])
    rows.append([Button.inline("🔎 پیگیری کد دیگر", PREFIX + b"input")])
    rows.append([Button.inline("🏠 داشبورد", PREFIX + b"home")])
    return rows


def _detail(row) -> tuple[str, list[list[Button]]]:
    order, checkout, subscription, tenant, registration = row
    tracking_code = registration.tracking_code
    payment_ref = checkout.payment_reference if checkout else None
    service_status = subscription.status if subscription else "ساخته نشده"
    service_id = subscription.provider_service_id if subscription else None
    text = (
        "🧾 **مدیریت کامل سفارش**\n\n"
        f"🆔 کد پیگیری: `{tracking_code}`\n"
        f"📦 شماره سفارش: `{order.id}`\n"
        f"📌 وضعیت سفارش: **{order.status}**\n"
        f"🤖 ربات نمایندگی: @{tenant.bot_username or '—'}\n"
        f"🆔 Bot ID: `{tenant.bot_id}`\n"
        f"👤 کاربر: `{order.telegram_user_id}`\n\n"
        f"📋 پلن: {order.plan_name}\n"
        f"📶 حجم: {order.volume_gb:g} GB\n"
        f"📅 مدت: {order.days} روز\n"
        f"💰 مبلغ: {_money(order.amount)}\n"
        f"💳 رسید/مرجع پرداخت: `{payment_ref or 'ثبت نشده'}`\n\n"
        f"⚙️ وضعیت سرویس: **{service_status}**\n"
        f"🔗 شناسه سرویس پاسارگارد: `{service_id or '—'}`\n"
        f"📅 شروع: {_dt(subscription.starts_at) if subscription else '—'}\n"
        f"⏳ انقضا: {_dt(subscription.expires_at) if subscription else '—'}\n\n"
        f"🕐 ایجاد سفارش: {_dt(order.created_at)}\n"
        f"🕐 آخرین بروزرسانی: {_dt(order.updated_at)}"
    )
    return text, _buttons(order, subscription, tracking_code)


async def order_tracking_callback(event):
    if not _is_admin(event):
        return
    data = bytes(event.data or b"")
    if not data.startswith(PREFIX):
        return
    await event.answer()
    try:
        action = data[len(PREFIX):].decode("utf-8")
        if action == "input":
            _AWAITING_TRACKING.add(event.sender_id)
            await event.edit("🔎 **پیگیری سفارش**\n\nکد پیگیری سفارش را ارسال کنید.\nمثال: `PG-Z74VB414`", buttons=[[Button.inline("🔙 داشبورد", PREFIX + b"home")]])
            return
        if action == "home":
            _AWAITING_TRACKING.discard(event.sender_id)
            from app.telegram.central.admin import dashboard_text, dashboard_buttons
            await event.edit(await dashboard_text(), buttons=dashboard_buttons())
            return
        if action.startswith("view:"):
            order_id = int(action.split(":", 1)[1])
            if SessionFactory is None:
                raise RuntimeError("DATABASE_URL is not configured")
            async with SessionFactory() as session:
                row = (await session.execute(
                    select(Order, CheckoutRecord, ServiceSubscription, TenantRecord, __import__('app.db.models', fromlist=['RepresentativeRegistration']).RepresentativeRegistration)
                    .outerjoin(CheckoutRecord, (CheckoutRecord.order_id == Order.id) & (CheckoutRecord.tenant_id == Order.tenant_id))
                    .outerjoin(ServiceSubscription, (ServiceSubscription.order_id == Order.id) & (ServiceSubscription.tenant_id == Order.tenant_id))
                    .join(TenantRecord, TenantRecord.id == Order.tenant_id)
                    .join(__import__('app.db.models', fromlist=['RepresentativeRegistration']).RepresentativeRegistration, __import__('app.db.models', fromlist=['RepresentativeRegistration']).RepresentativeRegistration.id == TenantRecord.registration_id)
                    .where(Order.id == order_id)
                )).first()
            if not row:
                raise LookupError("سفارش پیدا نشد.")
            text, buttons = _detail(row)
            await event.edit(text, buttons=buttons)
            return
        if ":" in action:
            action_name, value = action.split(":", 1)
            order_id = int(value)
            order = await _get_order(order_id)
            if order is None:
                raise LookupError("سفارش پیدا نشد.")
            if action_name == "paid":
                await _set_paid_admin(order_id)
                text = "💳 پرداخت توسط مدیریت مرکزی تأیید شد و سفارش آماده ساخت سرویس است."
            elif action_name == "provision":
                if order.status != "paid":
                    raise ValueError("ابتدا پرداخت سفارش را تأیید کنید.")
                subscription = await PasarguardProvisioningService().provision_paid_order(order.id, tenant_id=order.tenant_id)
                text = "⚡ سرویس در پاسارگارد ساخته و فعال شد." if subscription.status == "active" else "⚙️ ساخت سرویس انجام شد ولی هنوز فعال نشده است."
            elif action_name == "fulfilled":
                await _mark_fulfilled(order_id)
                text = "✅ سفارش تکمیل شد."
            elif action_name == "cancel":
                await _cancel_order(order_id)
                text = "🗑 سفارش لغو شد."
            else:
                raise LookupError("عملیات ناشناخته است.")
            if SessionFactory is None:
                raise RuntimeError("DATABASE_URL is not configured")
            async with SessionFactory() as session:
                from app.db.models import RepresentativeRegistration
                row = (await session.execute(select(Order, CheckoutRecord, ServiceSubscription, TenantRecord, RepresentativeRegistration).outerjoin(CheckoutRecord, (CheckoutRecord.order_id == Order.id) & (CheckoutRecord.tenant_id == Order.tenant_id)).outerjoin(ServiceSubscription, (ServiceSubscription.order_id == Order.id) & (ServiceSubscription.tenant_id == Order.tenant_id)).join(TenantRecord, TenantRecord.id == Order.tenant_id).join(RepresentativeRegistration, RepresentativeRegistration.id == TenantRecord.registration_id).where(Order.id == order_id))).first()
            detail, buttons = _detail(row)
            await event.edit(f"{text}\n\n{detail}", buttons=buttons)
            return
    except Exception as exc:
        print(f"[central-admin-orders] CALLBACK ERROR: {type(exc).__name__}: {exc}", flush=True)
        await event.edit(f"❌ عملیات سفارش انجام نشد.\n\n`{type(exc).__name__}: {exc}`", buttons=[[Button.inline("🔎 پیگیری کد دیگر", PREFIX + b"input")]])


async def order_tracking_text(event):
    if not _is_admin(event) or not event.raw_text:
        return
    if event.sender_id not in _AWAITING_TRACKING:
        return
    text = event.raw_text.strip().upper()
    if text == "/admin":
        return
    _AWAITING_TRACKING.discard(event.sender_id)
    if not text.startswith("PG-"):
        await event.respond("❌ کد پیگیری باید مثل `PG-Z74VB414` باشد.", buttons=[[Button.inline("🔎 دوباره وارد کردن", PREFIX + b"input")]])
        return
    try:
        row = await _find_tracking(text)
        if not row:
            await event.respond("❌ این کد پیگیری پیدا نشد.", buttons=[[Button.inline("🔎 دوباره وارد کردن", PREFIX + b"input")]])
            return
        detail, buttons = _detail(row)
        await event.respond(detail, buttons=buttons)
    except Exception as exc:
        print(f"[central-admin-orders] TRACKING ERROR: {type(exc).__name__}: {exc}", flush=True)
        await event.respond("❌ دریافت اطلاعات سفارش انجام نشد. دوباره تلاش کنید.", buttons=[[Button.inline("🔎 دوباره وارد کردن", PREFIX + b"input")]])

from __future__ import annotations

from telethon import Button, events

from app.core.exceptions import PermissionDenied
from app.db.models import RegistrationStatus, TenantStatus
from app.services.central_admin import CentralAdminService
from app.services.provisioning import ProvisioningService
from app.services.registration_store import RegistrationStore
from app.telegram.representative.registry import registry


SERVICE = CentralAdminService()
PROVISIONER = ProvisioningService()
REGISTRATIONS = RegistrationStore()
PREFIX = b"central:admin:"
_AWAITING_BOT_ID: set[int] = set()


def register_central_admin_handlers(client) -> None:
    print("[central-admin] registering handlers", flush=True)
    client.add_event_handler(admin_start, events.NewMessage(pattern=r"^/admin$"))
    client.add_event_handler(admin_text, events.NewMessage(incoming=True))
    client.add_event_handler(admin_callback, events.CallbackQuery())
    print("[central-admin] handlers registered", flush=True)


def is_admin(event) -> bool:
    return bool(event.is_private and SERVICE.is_admin(event.sender_id))


async def admin_start(event):
    print(f"[central-admin] /admin received sender={event.sender_id}", flush=True)
    if not is_admin(event):
        return
    _AWAITING_BOT_ID.discard(event.sender_id)
    await event.respond(await dashboard_text(), buttons=dashboard_buttons())


async def admin_text(event):
    if not is_admin(event) or not event.raw_text:
        return
    text = event.raw_text.strip()
    if text == "/admin":
        return

    if event.sender_id in _AWAITING_BOT_ID:
        _AWAITING_BOT_ID.discard(event.sender_id)
        if not text.isdigit():
            await event.respond("❌ شناسه ربات باید فقط عدد باشد.", buttons=dashboard_buttons())
            return
        try:
            bot_id = int(text)
            tenant = await SERVICE.get_tenant_by_bot_id(bot_id)
            if tenant is None:
                await event.respond("❌ هیچ ربات نمایندگی با این شناسه پیدا نشد.", buttons=dashboard_buttons())
                return
            await event.respond(tenant_detail_text(tenant, registry.is_running(tenant.id)), buttons=tenant_buttons(tenant.id, tenant.status))
        except Exception as exc:
            print(f"[central-admin] BOT ID LOOKUP ERROR: {type(exc).__name__}: {exc}", flush=True)
            await event.respond("❌ بررسی شناسه ربات انجام نشد.", buttons=dashboard_buttons())
        return

    if text.startswith("reject:"):
        parts = text.split(":", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            await event.respond("❌ فرمت رد صحیح نیست.", buttons=dashboard_buttons())
            return
        try:
            record = await SERVICE.reject(int(parts[1]), parts[2])
        except Exception:
            await event.respond("❌ رد درخواست انجام نشد.", buttons=dashboard_buttons())
            return
        await event.respond(f"✅ درخواست `{record.tracking_code}` رد شد.", buttons=dashboard_buttons())


async def admin_callback(event):
    raw_data = event.data
    try:
        data = bytes(raw_data or b"")
    except (TypeError, ValueError):
        data = b""

    print(f"[central-admin] CALLBACK RECEIVED sender={event.sender_id} data={data!r}", flush=True)
    if not data.startswith(PREFIX):
        return

    if not is_admin(event):
        print(f"[central-admin] CALLBACK DENIED sender={event.sender_id}", flush=True)
        await event.answer("دسترسی ندارید.", alert=True)
        return

    await event.answer()
    try:
        if data == PREFIX + b"home":
            _AWAITING_BOT_ID.discard(event.sender_id)
            await event.edit(await dashboard_text(), buttons=dashboard_buttons())
            return
        if data == PREFIX + b"pending":
            await event.edit(await pending_text(), buttons=await pending_buttons())
            return
        if data == PREFIX + b"bots":
            await event.edit(await bots_text(), buttons=await bots_buttons())
            return
        if data == PREFIX + b"lookup":
            _AWAITING_BOT_ID.add(event.sender_id)
            await event.edit(
                "🤖 **مدیریت ربات**\n\nشناسه عددی ربات نمایندگی را ارسال کنید:\n\nمثال: `123456789`",
                buttons=[[Button.inline("🔙 بازگشت", PREFIX + b"home")]],
            )
            return
        if data.startswith(PREFIX + b"view:"):
            registration_id = int(data.split(b":")[-1])
            record = await SERVICE.get(registration_id)
            if record is None:
                await event.edit("❌ درخواست پیدا نشد.", buttons=dashboard_buttons())
                return
            tenant = await SERVICE.get_tenant_by_bot_id(record.bot_id) if record.bot_id else None
            if tenant:
                await event.edit(tenant_detail_text(tenant, registry.is_running(tenant.id)), buttons=tenant_buttons(tenant.id, tenant.status))
            else:
                await event.edit(detail_text(record), buttons=detail_buttons(record.id, record.status))
            return
        if data.startswith(PREFIX + b"tenant:"):
            tenant_id = data.split(b":", 1)[1].decode("utf-8")
            tenant = await SERVICE.get_tenant(tenant_id)
            if tenant is None:
                await event.edit("❌ ربات پیدا نشد.", buttons=dashboard_buttons())
                return
            await event.edit(tenant_detail_text(tenant, registry.is_running(tenant.id)), buttons=tenant_buttons(tenant.id, tenant.status))
            return
        if data.startswith(PREFIX + b"disable:"):
            tenant_id = data.split(b":", 1)[1].decode("utf-8")
            tenant = await SERVICE.get_tenant(tenant_id)
            if tenant is None:
                await event.edit("❌ ربات پیدا نشد.", buttons=dashboard_buttons())
                return
            await registry.stop(tenant.id)
            tenant = await SERVICE.set_tenant_status(tenant.id, TenantStatus.SUSPENDED)
            await event.edit(
                "⛔ **ربات غیرفعال شد**\n\n" + tenant_detail_text(tenant, False),
                buttons=tenant_buttons(tenant.id, tenant.status),
            )
            try:
                await event.client.send_message(tenant.owner_id, "⛔ ربات نمایندگی شما توسط مدیریت مرکزی غیرفعال شد.")
            except Exception:
                pass
            return
        if data.startswith(PREFIX + b"enable:"):
            tenant_id = data.split(b":", 1)[1].decode("utf-8")
            tenant = await SERVICE.get_tenant(tenant_id)
            if tenant is None:
                await event.edit("❌ ربات پیدا نشد.", buttons=dashboard_buttons())
                return
            token = await SERVICE.get_tenant_bot_token(tenant.id)
            await registry.start(tenant.id, token)
            tenant = await SERVICE.set_tenant_status(tenant.id, TenantStatus.ACTIVE)
            await event.edit(
                "✅ **ربات فعال شد**\n\n" + tenant_detail_text(tenant, True),
                buttons=tenant_buttons(tenant.id, tenant.status),
            )
            try:
                await event.client.send_message(tenant.owner_id, "✅ ربات نمایندگی شما توسط مدیریت مرکزی دوباره فعال شد.")
            except Exception:
                pass
            return
        if data.startswith(PREFIX + b"approve:"):
            registration_id = int(data.split(b":")[-1])
            record = await SERVICE.approve(registration_id)
            await event.edit("⚙️ **در حال راه‌اندازی نمایندگی...**\n\n🤖 ربات اختصاصی نماینده در حال اتصال است...")
            try:
                result = await PROVISIONER.provision(record.id)
            except Exception:
                latest = await SERVICE.get(record.id)
                await event.edit(
                    "❌ **راه‌اندازی ناموفق بود**\n\nاطلاعات ثبت‌شده حفظ شده و می‌توانید دوباره تلاش کنید.",
                    buttons=detail_buttons(record.id, latest.status if latest else RegistrationStatus.FAILED.value),
                )
                return
            username = f"@{result.bot_username}" if result.bot_username else "ربات فعال"
            await event.edit(
                "✅ **نمایندگی با موفقیت فعال شد**\n\n"
                f"🆔 کد پیگیری: `{record.tracking_code}`\n"
                f"🤖 ربات: `{username}`\n"
                f"🏷 برند: {record.brand or '—'}",
                buttons=detail_buttons(record.id, RegistrationStatus.ACTIVE.value),
            )
            try:
                await event.client.send_message(record.owner_id, f"🎉 **ربات نمایندگی شما فعال شد!**\n\n🤖 {username}\n🏷 {record.brand or 'نمایندگی'}")
            except Exception:
                pass
            return
        if data.startswith(PREFIX + b"retry:"):
            registration_id = int(data.split(b":")[-1])
            record = await REGISTRATIONS.update(registration_id, status=RegistrationStatus.PROVISIONING.value)
            await event.edit("🔄 **تلاش مجدد برای راه‌اندازی...**")
            try:
                result = await PROVISIONER.provision(record.id)
            except Exception:
                latest = await SERVICE.get(record.id)
                await event.edit(
                    "❌ تلاش مجدد هم ناموفق بود.\n\nاطلاعات محفوظ است.",
                    buttons=detail_buttons(record.id, latest.status if latest else RegistrationStatus.FAILED.value),
                )
                return
            username = f"@{result.bot_username}" if result.bot_username else "ربات فعال"
            await event.edit("✅ **راه‌اندازی با موفقیت انجام شد**\n\n" f"🤖 `{username}`", buttons=detail_buttons(record.id, RegistrationStatus.ACTIVE.value))
            try:
                await event.client.send_message(record.owner_id, f"🎉 ربات نمایندگی شما فعال شد: {username}")
            except Exception:
                pass
            return
        if data.startswith(PREFIX + b"cancel:"):
            registration_id = int(data.split(b":")[-1])
            record = await REGISTRATIONS.get(registration_id)
            if record is None:
                await event.edit("❌ درخواست پیدا نشد.", buttons=dashboard_buttons())
                return
            await REGISTRATIONS.mark_rejected(record.id, None)
            await event.edit(
                "🗑 **درخواست لغو شد**\n\nدرخواست از صف بررسی حذف شد و نماینده می‌تواند دوباره درخواست جدید ثبت کند.",
                buttons=[[Button.inline("🔙 درخواست‌های در انتظار", PREFIX + b"pending")], [Button.inline("🏠 داشبورد", PREFIX + b"home")]],
            )
            try:
                await event.client.send_message(record.owner_id, "ℹ️ درخواست نمایندگی شما لغو شد. در صورت تمایل می‌توانید دوباره درخواست جدید ثبت کنید.")
            except Exception:
                pass
            return
        if data.startswith(PREFIX + b"reject_prompt:"):
            registration_id = int(data.split(b":")[-1])
            await event.edit(
                "❌ **رد درخواست**\n\n"
                f"شناسه درخواست: `{registration_id}`\n\n"
                "دلیل را در قالب زیر ارسال کنید:\n"
                f"`reject:{registration_id}:دلیل رد درخواست`",
                buttons=[[Button.inline("🔙 بازگشت", PREFIX + b"pending")]],
            )
            return
    except (ValueError, LookupError):
        await event.edit("❌ درخواست نامعتبر یا منقضی شده است.", buttons=dashboard_buttons())
    except PermissionDenied:
        await event.answer("دسترسی ندارید.", alert=True)
    except Exception as exc:
        print(f"[central-admin] CALLBACK ERROR: {type(exc).__name__}: {exc}", flush=True)
        await event.edit("❌ عملیات انجام نشد. دوباره تلاش کنید.", buttons=dashboard_buttons())


async def dashboard_text() -> str:
    pending = await SERVICE.pending()
    tenants = await SERVICE.tenants()
    active = sum(1 for t in tenants if t.status == TenantStatus.ACTIVE.value)
    suspended = sum(1 for t in tenants if t.status == TenantStatus.SUSPENDED.value)
    return (
        "🛡 **پنل مدیریت مرکزی**\n\n"
        f"⏳ درخواست‌های در انتظار: **{len(pending)}**\n"
        f"🟢 ربات‌های فعال: **{active}**\n"
        f"⛔ ربات‌های غیرفعال: **{suspended}**\n"
        f"🤖 مجموع نمایندگی‌ها: **{len(tenants)}**"
    )


def dashboard_buttons():
    return [
        [Button.inline("⏳ درخواست‌های در انتظار", PREFIX + b"pending")],
        [Button.inline("🤖 مدیریت ربات‌های نمایندگان", PREFIX + b"bots")],
        [Button.inline("🔎 مدیریت با شناسه ربات", PREFIX + b"lookup")],
    ]


async def pending_text() -> str:
    pending = await SERVICE.pending()
    if not pending:
        return "📭 **درخواست‌های در انتظار**\n\nدر حال حاضر هیچ درخواست معوقی وجود ندارد."
    lines = ["⏳ **درخواست‌های در انتظار بررسی**", ""]
    for index, record in enumerate(pending, 1):
        lines.append(f"{index}. `{record.tracking_code}` — {record.brand or 'بدون برند'} — مالک `{record.owner_id}`")
    return "\n".join(lines)


async def pending_buttons():
    pending = await SERVICE.pending()
    rows = [[Button.inline(f"🔎 {r.tracking_code}", PREFIX + f"view:{r.id}".encode())] for r in pending]
    rows.append([Button.inline("🔙 داشبورد", PREFIX + b"home")])
    return rows


async def bots_text() -> str:
    tenants = await SERVICE.tenants()
    if not tenants:
        return "🤖 **ربات‌های نمایندگان**\n\nهنوز هیچ نمایندگی فعالی ثبت نشده است."
    active = sum(1 for t in tenants if t.status == TenantStatus.ACTIVE.value)
    suspended = sum(1 for t in tenants if t.status == TenantStatus.SUSPENDED.value)
    return f"🤖 **مدیریت ربات‌های نمایندگان**\n\n🟢 فعال: **{active}**\n⛔ غیرفعال: **{suspended}**\n\nبرای مشاهده و مدیریت، ربات موردنظر را انتخاب کنید."


async def bots_buttons():
    tenants = await SERVICE.tenants()
    rows = []
    for tenant in tenants:
        state = "🟢" if tenant.status == TenantStatus.ACTIVE.value else "⛔"
        label = f"{state} {tenant.bot_username or tenant.bot_id}"
        rows.append([Button.inline(label[:60], PREFIX + f"tenant:{tenant.id}".encode())])
    rows.append([Button.inline("🔎 ورود با شناسه ربات", PREFIX + b"lookup")])
    rows.append([Button.inline("🔙 داشبورد", PREFIX + b"home")])
    return rows


def tenant_detail_text(tenant, runtime_running: bool) -> str:
    status = "🟢 فعال" if tenant.status == TenantStatus.ACTIVE.value else "⛔ غیرفعال"
    runtime = "🟢 در حال اجرا" if runtime_running else "🔴 متوقف"
    return (
        "🤖 **مدیریت ربات نمایندگی**\n\n"
        f"🏷 برند: **{tenant.brand}**\n"
        f"🆔 Bot ID: `{tenant.bot_id}`\n"
        f"👤 مالک: `{tenant.owner_id}`\n"
        f"🔗 Username: @{tenant.bot_username or '—'}\n"
        f"📌 وضعیت: **{status}**\n"
        f"⚙️ Runtime: **{runtime}**\n\n"
        "🔐 Token و API Key در پنل مرکزی نمایش داده نمی‌شوند."
    )


def tenant_buttons(tenant_id: str, status: str):
    action = "disable" if status == TenantStatus.ACTIVE.value else "enable"
    label = "⛔ غیرفعال کردن ربات" if action == "disable" else "🟢 فعال کردن ربات"
    return [
        [Button.inline(label, PREFIX + f"{action}:{tenant_id}".encode())],
        [Button.inline("🔙 لیست ربات‌ها", PREFIX + b"bots")],
        [Button.inline("🏠 داشبورد", PREFIX + b"home")],
    ]


def detail_text(record) -> str:
    return (
        "🔎 **جزئیات درخواست نمایندگی**\n\n"
        f"🆔 کد پیگیری: `{record.tracking_code}`\n"
        f"👤 مالک: `{record.owner_id}`\n"
        f"🏷 برند: {record.brand or '—'}\n"
        f"🤖 Bot ID: `{record.bot_id or '—'}`\n"
        f"🌐 پنل: `{record.panel_url or '—'}`\n"
        f"👤 کاربر پنل: `{record.panel_username or '—'}`\n"
        f"📌 وضعیت: `{record.status}`\n\n"
        "🔐 Token و API Key هرگز در پنل مرکزی نمایش داده نمی‌شوند."
    )


def detail_buttons(registration_id: int, status: str):
    rows = []
    if status == RegistrationStatus.PENDING.value:
        rows.append([Button.inline("✅ تأیید و شروع راه‌اندازی", PREFIX + f"approve:{registration_id}".encode())])
        rows.append([Button.inline("🗑 لغو درخواست", PREFIX + f"cancel:{registration_id}".encode())])
    elif status == RegistrationStatus.FAILED.value:
        rows.append([Button.inline("🔄 تلاش مجدد راه‌اندازی", PREFIX + f"retry:{registration_id}".encode())])
    rows.append([Button.inline("🔙 درخواست‌های در انتظار", PREFIX + b"pending")])
    return rows

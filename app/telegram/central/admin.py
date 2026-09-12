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
_AWAITING_OWNER_ID: dict[int, str] = {}
PAGE_SIZE = 12


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
    _AWAITING_OWNER_ID.pop(event.sender_id, None)
    await event.respond(await dashboard_text(), buttons=dashboard_buttons())


async def admin_text(event):
    if not is_admin(event) or not event.raw_text:
        return
    text = event.raw_text.strip()
    if text == "/admin":
        return await admin_start(event)

    if event.sender_id in _AWAITING_BOT_ID:
        _AWAITING_BOT_ID.discard(event.sender_id)
        if not text.isdigit():
            await event.respond("❌ شناسه ربات باید فقط عدد باشد.", buttons=dashboard_buttons())
            return
        try:
            tenant = await SERVICE.get_tenant_by_bot_id(int(text))
            if tenant is None:
                await event.respond("❌ هیچ ربات نمایندگی با این شناسه پیدا نشد.", buttons=dashboard_buttons())
                return
            await event.respond(tenant_detail_text(tenant, registry.is_running(tenant.id)), buttons=tenant_buttons(tenant.id, tenant.status, tenant.bot_id))
        except Exception as exc:
            print(f"[central-admin] BOT ID LOOKUP ERROR: {type(exc).__name__}: {exc}", flush=True)
            await event.respond("❌ بررسی شناسه ربات انجام نشد.", buttons=dashboard_buttons())
        return

    if event.sender_id in _AWAITING_OWNER_ID:
        tenant_id = _AWAITING_OWNER_ID.pop(event.sender_id)
        if not text.isdigit() or int(text) <= 0:
            await event.respond("❌ شناسه ادمین باید یک عدد معتبر باشد.", buttons=[[Button.inline("🔙 بازگشت", PREFIX + f"tenant:{tenant_id}".encode())]])
            return
        try:
            tenant = await SERVICE.change_tenant_owner(tenant_id, int(text))
            await event.respond(
                "✅ **ادمین پنل با موفقیت تغییر کرد.**\n\n"
                f"👤 ادمین جدید: `{tenant.owner_id}`\n\n"
                "از این پس پنل مدیریت ربات برای این شناسه در دسترس است.",
                buttons=tenant_buttons(tenant.id, tenant.status, tenant.bot_id),
            )
            try:
                await event.client.send_message(tenant.owner_id, "🛠 شما به عنوان ادمین پنل مدیریت ربات نمایندگی تعیین شدید.")
            except Exception:
                pass
        except Exception as exc:
            print(f"[central-admin] OWNER CHANGE ERROR: {type(exc).__name__}: {exc}", flush=True)
            await event.respond("❌ تغییر ادمین انجام نشد.", buttons=dashboard_buttons())
        return

    if text.startswith("reject:"):
        parts = text.split(":", 2)
        if len(parts) != 3 or not parts[1].isdigit():
            await event.respond("❌ فرمت رد صحیح نیست.", buttons=dashboard_buttons())
            return
        try:
            record = await SERVICE.reject(int(parts[1]), parts[2])
            await event.respond(f"✅ درخواست `{record.tracking_code}` رد شد.", buttons=dashboard_buttons())
        except Exception:
            await event.respond("❌ رد درخواست انجام نشد.", buttons=dashboard_buttons())


async def admin_callback(event):
    try:
        data = bytes(event.data or b"")
    except (TypeError, ValueError):
        data = b""
    print(f"[central-admin] CALLBACK RECEIVED sender={event.sender_id} data={data!r}", flush=True)
    if not data.startswith(PREFIX):
        return
    if not is_admin(event):
        await event.answer("دسترسی ندارید.", alert=True)
        return
    await event.answer()
    try:
        if data in (PREFIX + b"home", PREFIX + b"refresh"):
            _AWAITING_BOT_ID.discard(event.sender_id)
            _AWAITING_OWNER_ID.pop(event.sender_id, None)
            await event.edit(await dashboard_text(), buttons=dashboard_buttons())
            return
        if data == PREFIX + b"system":
            await event.edit(await system_text(), buttons=system_buttons())
            return
        if data == PREFIX + b"pending":
            await event.edit(await pending_text(0), buttons=await pending_buttons(0))
            return
        if data.startswith(PREFIX + b"pending:page:"):
            page = _page_from(data, b"pending:page:")
            await event.edit(await pending_text(page), buttons=await pending_buttons(page))
            return
        if data == PREFIX + b"bots":
            await event.edit(await bots_text(0), buttons=await bots_buttons(0))
            return
        if data.startswith(PREFIX + b"bots:page:"):
            page = _page_from(data, b"bots:page:")
            await event.edit(await bots_text(page), buttons=await bots_buttons(page))
            return
        if data == PREFIX + b"lookup":
            _AWAITING_BOT_ID.add(event.sender_id)
            _AWAITING_OWNER_ID.pop(event.sender_id, None)
            await event.edit("🤖 **ورود مستقیم به مدیریت ربات**\n\nشناسه عددی ربات نمایندگی را ارسال کنید:\n\nمثال: `123456789`", buttons=[[Button.inline("🔙 داشبورد", PREFIX + b"home")]])
            return
        if data.startswith(PREFIX + b"view:"):
            registration_id = int(data.split(b":")[-1])
            record = await SERVICE.get(registration_id)
            if record is None:
                await event.edit("❌ درخواست پیدا نشد.", buttons=dashboard_buttons())
                return
            tenant = await SERVICE.get_tenant_by_bot_id(record.bot_id) if record.bot_id else None
            if tenant:
                await event.edit(tenant_detail_text(tenant, registry.is_running(tenant.id)), buttons=tenant_buttons(tenant.id, tenant.status, tenant.bot_id))
            else:
                await event.edit(detail_text(record), buttons=detail_buttons(record.id, record.status))
            return
        if data.startswith(PREFIX + b"tenant:"):
            tenant = await SERVICE.get_tenant(data.split(b":", 2)[-1].decode())
            if tenant is None:
                await event.edit("❌ ربات پیدا نشد.", buttons=dashboard_buttons())
                return
            await event.edit(tenant_detail_text(tenant, registry.is_running(tenant.id)), buttons=tenant_buttons(tenant.id, tenant.status, tenant.bot_id))
            return
        if data.startswith(PREFIX + b"disable:"):
            ref = data.split(b":", 2)[-1].decode()
            tenant = await SERVICE.get_tenant(ref)
            if tenant is None:
                await event.edit("❌ ربات پیدا نشد.", buttons=dashboard_buttons())
                return
            await registry.stop(tenant.id)
            tenant = await SERVICE.set_tenant_status(tenant.id, TenantStatus.SUSPENDED)
            await event.edit("⛔ **ربات غیرفعال شد**\n\n" + tenant_detail_text(tenant, False), buttons=tenant_buttons(tenant.id, tenant.status, tenant.bot_id))
            try:
                await event.client.send_message(tenant.owner_id, "⛔ ربات نمایندگی شما توسط مدیریت مرکزی غیرفعال شد.")
            except Exception:
                pass
            return
        if data.startswith(PREFIX + b"enable:"):
            ref = data.split(b":", 2)[-1].decode()
            tenant = await SERVICE.get_tenant(ref)
            if tenant is None:
                await event.edit("❌ ربات پیدا نشد.", buttons=dashboard_buttons())
                return
            token = await SERVICE.get_tenant_bot_token(tenant.id)
            await registry.start(tenant.id, token)
            tenant = await SERVICE.set_tenant_status(tenant.id, TenantStatus.ACTIVE)
            await event.edit("✅ **ربات فعال شد**\n\n" + tenant_detail_text(tenant, True), buttons=tenant_buttons(tenant.id, tenant.status, tenant.bot_id))
            try:
                await event.client.send_message(tenant.owner_id, "✅ ربات نمایندگی شما توسط مدیریت مرکزی دوباره فعال شد.")
            except Exception:
                pass
            return
        if data.startswith(PREFIX + b"owner:"):
            ref = data.split(b":", 2)[-1].decode()
            tenant = await SERVICE.get_tenant(ref)
            if tenant is None:
                await event.edit("❌ ربات پیدا نشد.", buttons=dashboard_buttons())
                return
            _AWAITING_OWNER_ID[event.sender_id] = tenant.id
            _AWAITING_BOT_ID.discard(event.sender_id)
            await event.edit("👤 **تغییر ادمین پنل**\n\nشناسه عددی تلگرام ادمین جدید را ارسال کنید.\n\nمثال: `123456789`", buttons=[[Button.inline("🔙 بازگشت", PREFIX + f"tenant:{tenant.bot_id}".encode())]])
            return
        if data.startswith(PREFIX + b"delete_confirm:"):
            ref = data.split(b":", 2)[-1].decode()
            tenant = await SERVICE.get_tenant(ref)
            if tenant is None:
                await event.edit("❌ ربات پیدا نشد.", buttons=dashboard_buttons())
                return
            await event.edit("⚠️ **حذف ربات نمایندگی**\n\n" f"🤖 @{tenant.bot_username or '—'}\n" f"🆔 Bot ID: `{tenant.bot_id}`\n\n" "این عملیات ربات را متوقف و رکورد نمایندگی را از فهرست مدیریت مرکزی حذف می‌کند. سوابق فروش به صورت خودکار حذف نمی‌شوند.\n\nآیا مطمئن هستید؟", buttons=[[Button.inline("🗑 بله، حذف کن", PREFIX + f"delete:{tenant.bot_id}".encode())], [Button.inline("🔙 بازگشت", PREFIX + f"tenant:{tenant.bot_id}".encode())]])
            return
        if data.startswith(PREFIX + b"delete:"):
            ref = data.split(b":", 2)[-1].decode()
            tenant = await SERVICE.get_tenant(ref)
            if tenant is None:
                await event.edit("❌ ربات پیدا نشد.", buttons=dashboard_buttons())
                return
            owner_id, username = tenant.owner_id, tenant.bot_username
            await registry.stop(tenant.id)
            await SERVICE.delete_tenant(tenant.id)
            await event.edit("🗑 **ربات با موفقیت حذف شد**\n\n" f"🤖 @{username or '—'}\n" f"👤 ادمین قبلی: `{owner_id}`", buttons=dashboard_buttons())
            try:
                await event.client.send_message(owner_id, "⚠️ ربات نمایندگی شما توسط مدیریت مرکزی حذف شد و دیگر فعال نیست.")
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
                await event.edit("❌ **راه‌اندازی ناموفق بود**\n\nاطلاعات ثبت‌شده حفظ شده و می‌توانید دوباره تلاش کنید.", buttons=detail_buttons(record.id, latest.status if latest else RegistrationStatus.FAILED.value))
                return
            username = f"@{result.bot_username}" if result.bot_username else "ربات فعال"
            await event.edit("✅ **نمایندگی با موفقیت فعال شد**\n\n" f"🆔 کد پیگیری: `{record.tracking_code}`\n" f"🤖 ربات: `{username}`\n" f"🏷 برند: {record.brand or 'نمایندگی'}", buttons=detail_buttons(record.id, RegistrationStatus.ACTIVE.value))
            try:
                await event.client.send_message(record.owner_id, f"🎉 ربات نمایندگی شما فعال شد!\n\n🤖 {username}\n🏷 {record.brand or 'نمایندگی'}")
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
                await event.edit("❌ تلاش مجدد ناموفق بود. اطلاعات محفوظ است.", buttons=detail_buttons(record.id, latest.status if latest else RegistrationStatus.FAILED.value))
                return
            username = f"@{result.bot_username}" if result.bot_username else "ربات فعال"
            await event.edit("✅ **راه‌اندازی با موفقیت انجام شد**\n\n" f"🤖 `{username}`", buttons=detail_buttons(record.id, RegistrationStatus.ACTIVE.value))
            return
        if data.startswith(PREFIX + b"cancel:"):
            registration_id = int(data.split(b":")[-1])
            record = await REGISTRATIONS.get(registration_id)
            if record is None:
                await event.edit("❌ درخواست پیدا نشد.", buttons=dashboard_buttons())
                return
            await REGISTRATIONS.mark_rejected(record.id, None)
            await event.edit("🗑 **درخواست لغو شد**\n\nدرخواست از صف بررسی حذف شد و نماینده می‌تواند دوباره درخواست جدید ثبت کند.", buttons=[[Button.inline("🔙 درخواست‌ها", PREFIX + b"pending")], [Button.inline("🏠 داشبورد", PREFIX + b"home")]])
            try:
                await event.client.send_message(record.owner_id, "ℹ️ درخواست نمایندگی شما لغو شد. می‌توانید دوباره درخواست جدید ثبت کنید.")
            except Exception:
                pass
            return
        if data.startswith(PREFIX + b"reject_prompt:"):
            registration_id = int(data.split(b":")[-1])
            await event.edit("❌ **رد درخواست**\n\n" f"شناسه درخواست: `{registration_id}`\n\nدلیل را به صورت `reject:{registration_id}:دلیل` ارسال کنید.", buttons=[[Button.inline("🔙 بازگشت", PREFIX + b"pending")]])
            return
    except (ValueError, LookupError):
        await event.edit("❌ درخواست نامعتبر یا منقضی شده است.", buttons=dashboard_buttons())
    except PermissionDenied:
        await event.answer("دسترسی ندارید.", alert=True)
    except Exception as exc:
        print(f"[central-admin] CALLBACK ERROR: {type(exc).__name__}: {exc}", flush=True)
        await event.edit("❌ عملیات انجام نشد. دوباره تلاش کنید.", buttons=dashboard_buttons())


def _page_from(data: bytes, marker: bytes) -> int:
    return max(0, int(data[len(PREFIX) + len(marker):].decode()))


async def dashboard_text() -> str:
    pending = await SERVICE.pending()
    tenants = await SERVICE.tenants()
    active = sum(1 for t in tenants if t.status == TenantStatus.ACTIVE.value)
    suspended = sum(1 for t in tenants if t.status == TenantStatus.SUSPENDED.value)
    running = sum(1 for t in tenants if registry.is_running(t.id))
    return ("🛡 **پنل مدیریت مرکزی**\n\n"
            f"⏳ درخواست‌های در انتظار: **{len(pending)}**\n"
            f"🟢 ربات‌های فعال: **{active}**\n"
            f"⛔ ربات‌های غیرفعال: **{suspended}**\n"
            f"⚙️ Runtime در حال اجرا: **{running}**\n"
            f"🤖 مجموع نمایندگی‌ها: **{len(tenants)}**\n\n"
            "مدیریت کامل درخواست‌ها، ربات‌ها و سفارش‌ها از همین پنل انجام می‌شود.")


def dashboard_buttons():
    return [
        [Button.inline("⏳ درخواست‌های در انتظار", PREFIX + b"pending")],
        [Button.inline("🤖 مدیریت ربات‌های نمایندگان", PREFIX + b"bots")],
        [Button.inline("🔎 ورود مستقیم با Bot ID", PREFIX + b"lookup")],
        [Button.inline("🩺 وضعیت و سلامت سیستم", PREFIX + b"system")],
        [Button.inline("🔄 بروزرسانی داشبورد", PREFIX + b"refresh")],
    ]


async def system_text() -> str:
    try:
        tenants = await SERVICE.tenants()
        pending = await SERVICE.pending()
        running = sum(1 for t in tenants if registry.is_running(t.id))
        return ("🩺 **وضعیت سیستم مرکزی**\n\n"
                "🟢 Database: قابل دسترس\n"
                "🟢 Central Bot: در حال اجرا\n"
                f"⚙️ Runtime فعال: **{running}/{len(tenants)}**\n"
                f"⏳ درخواست معوق: **{len(pending)}**\n"
                f"🤖 کل نمایندگی‌ها: **{len(tenants)}**\n\n"
                "🔐 Token/API Key در پنل نمایش داده نمی‌شود.\n"
                "📈 لیست‌ها صفحه‌بندی شده‌اند تا برای تعداد زیاد ربات هم قابل استفاده باشند.")
    except Exception as exc:
        return f"🔴 **خطا در بررسی سیستم**\n\n`{type(exc).__name__}: {exc}`"


def system_buttons():
    return [[Button.inline("🔄 بررسی مجدد", PREFIX + b"system")], [Button.inline("🏠 داشبورد", PREFIX + b"home")]]


async def pending_text(page: int) -> str:
    pending = await SERVICE.pending()
    total = len(pending)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(0, page), total_pages - 1)
    items = pending[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    if not items:
        return "📭 **درخواست‌های در انتظار**\n\nدر حال حاضر هیچ درخواست معوقی وجود ندارد."
    lines = [f"⏳ **درخواست‌های در انتظار** — صفحه {page + 1}/{total_pages}", ""]
    for index, record in enumerate(items, page * PAGE_SIZE + 1):
        lines.append(f"{index}. `{record.tracking_code}` — {record.brand or 'بدون برند'} — مالک `{record.owner_id}`")
    return "\n".join(lines)


async def pending_buttons(page: int):
    pending = await SERVICE.pending()
    total_pages = max(1, (len(pending) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(0, page), total_pages - 1)
    items = pending[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    rows = [[Button.inline(f"🔎 {r.tracking_code}", PREFIX + f"view:{r.id}".encode())] for r in items]
    nav = []
    if page > 0:
        nav.append(Button.inline("⬅️ قبلی", PREFIX + f"pending:page:{page - 1}".encode()))
    if page + 1 < total_pages:
        nav.append(Button.inline("بعدی ➡️", PREFIX + f"pending:page:{page + 1}".encode()))
    if nav:
        rows.append(nav)
    rows.append([Button.inline("🔄 بروزرسانی", PREFIX + f"pending:page:{page}".encode())])
    rows.append([Button.inline("🏠 داشبورد", PREFIX + b"home")])
    return rows


async def bots_text(page: int) -> str:
    tenants = await SERVICE.tenants()
    if not tenants:
        return "🤖 **ربات‌های نمایندگان**\n\nهنوز هیچ نمایندگی ثبت نشده است."
    active = sum(1 for t in tenants if t.status == TenantStatus.ACTIVE.value)
    suspended = sum(1 for t in tenants if t.status == TenantStatus.SUSPENDED.value)
    total_pages = max(1, (len(tenants) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(0, page), total_pages - 1)
    return (f"🤖 **مدیریت ربات‌های نمایندگان** — صفحه {page + 1}/{total_pages}\n\n"
            f"🟢 فعال: **{active}**\n⛔ غیرفعال: **{suspended}**\n📦 کل: **{len(tenants)}**\n\nربات موردنظر را انتخاب کنید.")


async def bots_buttons(page: int):
    tenants = await SERVICE.tenants()
    total_pages = max(1, (len(tenants) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(0, page), total_pages - 1)
    items = tenants[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    rows = []
    for tenant in items:
        state = "🟢" if tenant.status == TenantStatus.ACTIVE.value else "⛔"
        runtime = "⚡" if registry.is_running(tenant.id) else "⏹"
        label = f"{state}{runtime} {tenant.bot_username or tenant.bot_id}"
        rows.append([Button.inline(label[:60], PREFIX + f"tenant:{tenant.bot_id}".encode())])
    nav = []
    if page > 0:
        nav.append(Button.inline("⬅️ قبلی", PREFIX + f"bots:page:{page - 1}".encode()))
    if page + 1 < total_pages:
        nav.append(Button.inline("بعدی ➡️", PREFIX + f"bots:page:{page + 1}".encode()))
    if nav:
        rows.append(nav)
    rows.append([Button.inline("🔎 ورود با Bot ID", PREFIX + b"lookup")])
    rows.append([Button.inline("🔄 بروزرسانی", PREFIX + f"bots:page:{page}".encode())])
    rows.append([Button.inline("🏠 داشبورد", PREFIX + b"home")])
    return rows


def tenant_detail_text(tenant, runtime_running: bool) -> str:
    status = "🟢 فعال" if tenant.status == TenantStatus.ACTIVE.value else "⛔ غیرفعال"
    runtime = "🟢 در حال اجرا" if runtime_running else "🔴 متوقف"
    return ("🤖 **مدیریت ربات نمایندگی**\n\n"
            f"🏷 برند: **{tenant.brand}**\n"
            f"🆔 Bot ID: `{tenant.bot_id}`\n"
            f"👤 ادمین پنل: `{tenant.owner_id}`\n"
            f"🔗 Username: @{tenant.bot_username or '—'}\n"
            f"📌 وضعیت: **{status}**\n"
            f"⚙️ Runtime: **{runtime}**\n\n"
            "🔐 Token و API Key در پنل مرکزی نمایش داده نمی‌شوند.")


def tenant_buttons(tenant_id: str, status: str, bot_id: int | None = None):
    ref = str(bot_id) if bot_id is not None else str(tenant_id)
    action = "disable" if status == TenantStatus.ACTIVE.value else "enable"
    label = "⛔ غیرفعال کردن ربات" if action == "disable" else "🟢 فعال کردن ربات"
    return [[Button.inline(label, PREFIX + f"{action}:{ref}".encode())],
            [Button.inline("👤 تغییر ادمین پنل", PREFIX + f"owner:{ref}".encode())],
            [Button.inline("🗑 حذف ربات", PREFIX + f"delete_confirm:{ref}".encode())],
            [Button.inline("🔙 لیست ربات‌ها", PREFIX + b"bots")],
            [Button.inline("🏠 داشبورد", PREFIX + b"home")]]


def detail_text(record) -> str:
    return ("🔎 **جزئیات درخواست نمایندگی**\n\n"
            f"🆔 کد پیگیری: `{record.tracking_code}`\n"
            f"👤 مالک: `{record.owner_id}`\n"
            f"🏷 برند: {record.brand or '—'}\n"
            f"🤖 Bot ID: `{record.bot_id or '—'}`\n"
            f"🌐 پنل: `{record.panel_url or '—'}`\n"
            f"👤 کاربر پنل: `{record.panel_username or '—'}`\n"
            f"📌 وضعیت: `{record.status}`\n\n"
            "🔐 Token و API Key هرگز در پنل مرکزی نمایش داده نمی‌شوند.")


def detail_buttons(registration_id: int, status: str):
    rows = []
    if status == RegistrationStatus.PENDING.value:
        rows.append([Button.inline("✅ تأیید و شروع راه‌اندازی", PREFIX + f"approve:{registration_id}".encode())])
        rows.append([Button.inline("🗑 لغو درخواست", PREFIX + f"cancel:{registration_id}".encode())])
    elif status == RegistrationStatus.FAILED.value:
        rows.append([Button.inline("🔄 تلاش مجدد راه‌اندازی", PREFIX + f"retry:{registration_id}".encode())])
    rows.append([Button.inline("🔙 درخواست‌ها", PREFIX + b"pending")])
    rows.append([Button.inline("🏠 داشبورد", PREFIX + b"home")])
    return rows

from __future__ import annotations

from telethon import Button, events

from app.core.config import settings
from app.core.exceptions import PermissionDenied
from app.db.models import RegistrationStatus
from app.services.central_admin import CentralAdminService


SERVICE = CentralAdminService()
PREFIX = b"central:admin:"


def register_central_admin_handlers(client) -> None:
    client.add_event_handler(admin_start, events.NewMessage(pattern=r"^/admin$"))
    client.add_event_handler(admin_text, events.NewMessage(incoming=True))
    client.add_event_handler(admin_callback, events.CallbackQuery(data=PREFIX))


def is_admin(event) -> bool:
    return bool(event.is_private and SERVICE.is_admin(event.sender_id))


async def admin_start(event):
    if not is_admin(event):
        return
    await event.respond(await dashboard_text(), buttons=dashboard_buttons())


async def admin_text(event):
    if not is_admin(event) or not event.raw_text:
        return
    text = event.raw_text.strip()
    if text == "/admin":
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
    if not is_admin(event):
        await event.answer("دسترسی ندارید.", alert=True)
        return
    data = event.data
    await event.answer()
    try:
        if data == PREFIX + b"home":
            await event.edit(await dashboard_text(), buttons=dashboard_buttons())
            return
        if data == PREFIX + b"pending":
            await event.edit(await pending_text(), buttons=await pending_buttons())
            return
        if data.startswith(PREFIX + b"view:"):
            registration_id = int(data.split(b":")[-1])
            record = await SERVICE.get(registration_id)
            if record is None:
                await event.edit("❌ درخواست پیدا نشد.", buttons=dashboard_buttons())
                return
            await event.edit(detail_text(record), buttons=detail_buttons(record.id, record.status))
            return
        if data.startswith(PREFIX + b"approve:"):
            registration_id = int(data.split(b":")[-1])
            record = await SERVICE.approve(registration_id)
            await event.edit(
                "⚙️ **درخواست وارد مرحله راه‌اندازی شد**\n\n"
                f"🆔 `{record.tracking_code}`\n\n"
                "Tenant و ربات نمایندگی در مرحله Provisioning ایجاد می‌شوند.",
                buttons=detail_buttons(record.id, record.status),
            )
            try:
                await event.client.send_message(record.owner_id, user_approved_text(record))
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
    except Exception:
        await event.edit("❌ عملیات انجام نشد. دوباره تلاش کنید.", buttons=dashboard_buttons())


async def dashboard_text() -> str:
    pending = await SERVICE.pending()
    return (
        "🛡 **مدیریت مرکزی نمایندگان**\n\n"
        f"⏳ درخواست‌های در انتظار: **{len(pending)}**\n\n"
        "از این بخش درخواست‌های نمایندگی را بررسی و برای راه‌اندازی تأیید یا رد کنید."
    )


def dashboard_buttons():
    return [
        [Button.inline("⏳ درخواست‌های در انتظار", PREFIX + b"pending")],
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
        rows.append([Button.inline("❌ رد درخواست", PREFIX + f"reject_prompt:{registration_id}".encode())])
    rows.append([Button.inline("🔙 درخواست‌های در انتظار", PREFIX + b"pending")])
    return rows


def user_approved_text(record) -> str:
    return (
        "✅ **درخواست نمایندگی تأیید شد**\n\n"
        f"🆔 کد پیگیری: `{record.tracking_code}`\n\n"
        "درخواست وارد مرحله راه‌اندازی شده است. پس از آماده‌شدن ربات، اطلاعات ورود برای شما ارسال می‌شود."
    )

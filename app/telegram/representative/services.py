from __future__ import annotations

from datetime import datetime, timezone

from telethon import Button, events

from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.pasarguard_provisioning import PasarguardProvisioningService
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.subscriptions import SERVICE

PREFIX = b"rep:services:"
ENTRY = b"rep:rep.services"
BACK = b"rep:rep.home"
DASHBOARD = RepresentativeDashboardService()

FILTERS = {
    "all": "همه",
    "active": "فعال",
    "pending_provisioning": "در انتظار تحویل",
    "provisioning": "در حال ساخت",
    "expired": "منقضی",
    "revoked": "لغوشده",
}
LABELS = {
    "pending_provisioning": "⏳ در انتظار تحویل",
    "provisioning": "🔄 در حال ساخت",
    "active": "🟢 فعال",
    "expired": "⚫ منقضی",
    "revoked": "🔴 لغوشده",
}


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            await callback_handler(event)

    client.add_event_handler(
        callback,
        events.CallbackQuery(func=lambda e: bool(e.data and (e.data.startswith(PREFIX) or e.data == ENTRY))),
    )


def _status(item):
    if item.status == "active" and item.expires_at:
        expiry = item.expires_at.replace(tzinfo=timezone.utc) if item.expires_at.tzinfo is None else item.expires_at
        if expiry <= datetime.now(timezone.utc):
            return "expired"
    return item.status


def _date(value):
    if not value:
        return "—"
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


async def _authorized(event):
    return bool(event.is_private and get_tenant() and await DASHBOARD.is_owner(event.sender_id))


async def _rows(status="all"):
    rows = await SERVICE.list_for_tenant(limit=100)
    if status != "all":
        rows = [item for item in rows if _status(item) == status]
    return rows


async def render(status="all"):
    if status not in FILTERS:
        status = "all"
    rows = await _rows(status)
    title = FILTERS[status]
    if not rows:
        text = f"🔌 **مدیریت سرویس‌ها**\n\nفیلتر: **{title}**\n\nسرویسی در این بخش وجود ندارد."
    else:
        lines = ["🔌 **مدیریت سرویس‌ها**", f"فیلتر: **{title}**", ""]
        for item in rows:
            state = _status(item)
            lines.append(f"#{item.id} — کاربر `{item.telegram_user_id}` — {item.plan_name} — {LABELS.get(state, state)}")
        text = "\n".join(lines)
    buttons = [
        [Button.inline("📋 همه", PREFIX + b"filter:all"), Button.inline("🟢 فعال", PREFIX + b"filter:active")],
        [Button.inline("⏳ انتظار", PREFIX + b"filter:pending_provisioning"), Button.inline("🔄 ساخت", PREFIX + b"filter:provisioning")],
        [Button.inline("⚫ منقضی", PREFIX + b"filter:expired"), Button.inline("🔴 لغوشده", PREFIX + b"filter:revoked")],
    ]
    for item in rows[:30]:
        state = _status(item)
        buttons.append([Button.inline(f"#{item.id} | {LABELS.get(state, state)} | {item.plan_name}", PREFIX + f"view:{item.id}:{status}".encode())])
    buttons.append([Button.inline("🔄 بروزرسانی", PREFIX + f"filter:{status}".encode())])
    buttons.append([Button.inline("🔙 داشبورد", BACK)])
    return text, buttons


async def _detail(item):
    state = _status(item)
    text = (
        f"🔌 **سرویس #{item.id}**\n\n"
        f"👤 کاربر: `{item.telegram_user_id}`\n"
        f"🧾 سفارش: `#{item.order_id}`\n"
        f"📦 پلن: **{item.plan_name}**\n"
        f"💾 حجم: **{item.volume_gb:g} GB**\n"
        f"📅 مدت: **{item.days} روز**\n"
        f"📊 وضعیت: **{LABELS.get(state, state)}**\n"
        f"🟢 شروع: **{_date(item.starts_at)}**\n"
        f"⏰ انقضا: **{_date(item.expires_at)}**\n"
        f"🆔 شناسه پاسارگارد: `{item.provider_service_id or '—'}`\n"
        f"🔗 لینک اشتراک: **{'آماده' if item.subscription_url else 'ثبت نشده'}**"
    )
    return text


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
        if status not in FILTERS:
            return await event.answer("فیلتر نامعتبر است.", alert=True)
        text, buttons = await render(status)
        await event.edit(text, buttons=buttons)
        return await event.answer()

    if action.startswith("view:"):
        parts = action.split(":")
        try:
            sid = int(parts[1])
        except (IndexError, ValueError):
            return await event.answer("شناسه سرویس نامعتبر است.", alert=True)
        previous = parts[2] if len(parts) > 2 and parts[2] in FILTERS else "all"
        item = await SERVICE.get(sid)
        if item is None:
            return await event.answer("سرویس پیدا نشد.", alert=True)
        state = _status(item)
        rows = []
        if state in {"pending_provisioning", "provisioning"} and item.order_id:
            rows.append([Button.inline("🔌 تحویل / تلاش مجدد", PREFIX + f"retry:{sid}:{previous}".encode())])
        if state == "active":
            rows.append([Button.inline("⚫ ثبت انقضا", PREFIX + f"expire:{sid}:{previous}".encode())])
            rows.append([Button.inline("🔴 لغو دسترسی", PREFIX + f"revoke:{sid}:{previous}".encode())])
        rows.append([Button.inline("🔄 بروزرسانی", PREFIX + f"view:{sid}:{previous}".encode())])
        rows.append([Button.inline("📋 لیست سرویس‌ها", PREFIX + f"filter:{previous}".encode())])
        rows.append([Button.inline("📊 داشبورد", BACK)])
        await event.edit(await _detail(item), buttons=rows)
        return await event.answer()

    if action.startswith("retry:"):
        parts = action.split(":")
        try:
            sid = int(parts[1])
        except (IndexError, ValueError):
            return await event.answer("شناسه سرویس نامعتبر است.", alert=True)
        previous = parts[2] if len(parts) > 2 and parts[2] in FILTERS else "all"
        item = await SERVICE.get(sid)
        if item is None:
            return await event.answer("سرویس پیدا نشد.", alert=True)
        try:
            item = await PasarguardProvisioningService().provision_paid_order(item.order_id)
        except Exception as exc:
            return await event.answer(f"تحویل ناموفق: {str(exc)[:180]}", alert=True)
        await event.answer("✅ فرآیند تحویل اجرا شد.")
        current = await SERVICE.get(sid)
        buttons = [[Button.inline("🔄 بروزرسانی", PREFIX + f"view:{sid}:{previous}".encode())], [Button.inline("📋 لیست", PREFIX + f"filter:{previous}".encode())]]
        await event.edit(await _detail(current), buttons=buttons)
        return

    if action.startswith("expire:"):
        parts = action.split(":")
        try:
            sid = int(parts[1])
        except (IndexError, ValueError):
            return await event.answer("شناسه سرویس نامعتبر است.", alert=True)
        previous = parts[2] if len(parts) > 2 and parts[2] in FILTERS else "all"
        try:
            item = await SERVICE.mark_expired(sid)
        except (LookupError, ValueError) as exc:
            return await event.answer(str(exc), alert=True)
        await event.answer("⚫ سرویس به‌عنوان منقضی ثبت شد.")
        await event.edit(await _detail(item), buttons=[[Button.inline("📋 لیست", PREFIX + f"filter:{previous}".encode())], [Button.inline("📊 داشبورد", BACK)]])
        return

    if action.startswith("revoke:"):
        parts = action.split(":")
        try:
            sid = int(parts[1])
        except (IndexError, ValueError):
            return await event.answer("شناسه سرویس نامعتبر است.", alert=True)
        previous = parts[2] if len(parts) > 2 and parts[2] in FILTERS else "all"
        try:
            item = await SERVICE.revoke(sid, event.sender_id)
        except (LookupError, ValueError) as exc:
            return await event.answer(str(exc), alert=True)
        await event.answer("🔴 دسترسی سرویس در سیستم لغو شد.")
        await event.edit(await _detail(item) + "\n\n⚠️ این عملیات وضعیت سرویس را در سیستم فروش تغییر می‌دهد؛ ابطال واقعی در پنل پاسارگارد فقط در صورت وجود API ابطال جداگانه انجام می‌شود.", buttons=[[Button.inline("📋 لیست", PREFIX + f"filter:{previous}".encode())], [Button.inline("📊 داشبورد", BACK)]])
        return

    await event.answer("گزینه نامعتبر است.", alert=True)

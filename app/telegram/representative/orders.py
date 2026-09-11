from __future__ import annotations

from telethon import Button, events

from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.orders import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService

PREFIX = b"rep:orders:"
ENTRY = b"rep:rep.orders"
BACK = b"rep:rep.home"
DASHBOARD = RepresentativeDashboardService()
STATUS_LABELS = {"pending": "🟡 در انتظار پرداخت", "paid": "🔵 پرداخت‌شده", "fulfilled": "🟢 تکمیل‌شده", "cancelled": "🔴 لغوشده"}


def register(client, tenant_id: str | None = None) -> None:
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            await callback_handler(event)
    client.add_event_handler(callback, events.CallbackQuery(data=PREFIX))
    client.add_event_handler(callback, events.CallbackQuery(data=ENTRY))


def _status(value: str) -> str:
    return STATUS_LABELS.get(value, value)


def _detail(order) -> str:
    return (f"🛒 **سفارش #{order.id}**\n\n👤 کاربر: `{order.telegram_user_id}`\n📦 پلن: **{order.plan_name}**\n💾 حجم: `{order.volume_gb:g} GB`\n⏱ مدت: `{order.days}` روز\n💰 مبلغ: **{order.amount:,.2f}**\n📌 وضعیت: **{_status(order.status)}**")


async def render() -> tuple[str, list]:
    orders = await SERVICE.list()
    if not orders:
        return "🛒 **فروش و سفارش‌ها**\n\nهنوز سفارشی ثبت نشده است.", [[Button.inline("🔙 داشبورد", BACK)]]
    lines = ["🛒 **فروش و سفارش‌ها**", ""]
    buttons = []
    for order in orders:
        lines.append(f"#{order.id} — {order.plan_name} — {order.amount:,.2f} — {_status(order.status)}")
        buttons.append([Button.inline(f"#{order.id} | {_status(order.status)}", PREFIX + f"view:{order.id}".encode())])
    buttons.append([Button.inline("🔙 داشبورد", BACK)])
    return "\n".join(lines), buttons


async def _authorized(event) -> bool:
    return bool(event.is_private and get_tenant() and await DASHBOARD.is_owner(event.sender_id))


async def callback_handler(event) -> None:
    if not await _authorized(event):
        await event.answer("دسترسی مدیریت ندارید.", alert=True)
        return
    if event.data == ENTRY:
        text, buttons = await render()
        await event.edit(text, buttons=buttons); await event.answer(); return
    action = event.data[len(PREFIX):].decode(errors="ignore")
    if action in {"", "list"}:
        text, buttons = await render(); await event.edit(text, buttons=buttons); await event.answer(); return
    if action.startswith("view:"):
        order = await SERVICE.get(int(action.split(":", 1)[1]))
        if order is None:
            await event.answer("سفارش پیدا نشد.", alert=True); return
        rows = []
        if order.status == "pending":
            rows += [[Button.inline("💳 تأیید پرداخت", PREFIX + f"status:{order.id}:paid".encode())], [Button.inline("❌ لغو سفارش", PREFIX + f"status:{order.id}:cancelled".encode())]]
        elif order.status == "paid":
            rows += [[Button.inline("📦 تکمیل سفارش", PREFIX + f"status:{order.id}:fulfilled".encode())], [Button.inline("❌ لغو سفارش", PREFIX + f"status:{order.id}:cancelled".encode())]]
        rows += [[Button.inline("🛒 لیست سفارش‌ها", PREFIX + b"list")], [Button.inline("📊 داشبورد", BACK)]]
        await event.edit(_detail(order), buttons=rows); await event.answer(); return
    if action.startswith("status:"):
        _, order_id, status = action.split(":")
        try:
            order = await SERVICE.set_status(int(order_id), status)
        except (LookupError, ValueError) as exc:
            await event.answer(str(exc), alert=True); return
        await event.edit(_detail(order) + "\n\n✅ وضعیت سفارش تغییر کرد.", buttons=[[Button.inline("🛒 سفارش‌ها", PREFIX + b"list")]])
        await event.answer(); return
    await event.answer("گزینه نامعتبر است.", alert=True)

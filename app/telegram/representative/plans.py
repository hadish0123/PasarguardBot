from __future__ import annotations

from telethon import Button, events

from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.plans import PlanService
from app.services.representative_dashboard import RepresentativeDashboardService

PREFIX = b"rep:plans:"
SERVICE = PlanService()
DASHBOARD = RepresentativeDashboardService()
_STATES: dict[tuple[str, int], dict[str, object]] = {}


def register(client, tenant_id: str | None = None) -> None:
    async def text_handler(event):
        async with tenant_dispatch(tenant_id):
            await plan_text(event)
    async def callback_handler(event):
        async with tenant_dispatch(tenant_id):
            await plan_callback(event)
    client.add_event_handler(text_handler, events.NewMessage(incoming=True))
    client.add_event_handler(callback_handler, events.CallbackQuery(data=PREFIX))


async def _owner(event) -> bool:
    return bool(event.is_private and get_tenant() and await DASHBOARD.is_owner(event.sender_id))


async def render() -> tuple[str, list]:
    plans = await SERVICE.list()
    if not plans:
        text = "🗂 **مدیریت پلن‌ها**\n\nهنوز پلنی ساخته نشده است."
    else:
        lines = ["🗂 **مدیریت پلن‌ها**", ""]
        for plan in plans:
            state = "🟢 فعال" if plan.enabled else "🔴 غیرفعال"
            lines.append(f"#{plan.id} — **{plan.name}**\n💾 {plan.volume_gb:g} GB | ⏱ {plan.days} روز | 💰 {plan.price:g}\n{state}")
        text = "\n\n".join(lines)
    rows = [[Button.inline("➕ ساخت پلن", PREFIX + b"add")]]
    for plan in plans:
        rows.append([Button.inline(f"{('🟢' if plan.enabled else '🔴')} {plan.name}", PREFIX + f"view:{plan.id}".encode()), Button.inline("🔄", PREFIX + f"toggle:{plan.id}".encode())])
    rows.append([Button.inline("🔙 داشبورد", b"rep:rep.home")])
    return text, rows


async def show(event) -> None:
    if not await _owner(event):
        await event.answer("دسترسی ندارید.", alert=True); return
    text, buttons = await render()
    await event.edit(text, buttons=buttons); await event.answer()


async def plan_callback(event) -> None:
    if not await _owner(event):
        await event.answer("دسترسی ندارید.", alert=True); return
    action = event.data[len(PREFIX):].decode(errors="ignore")
    if action in {"list", ""}:
        await show(event); return
    if action == "add":
        _STATES[(get_tenant(), event.sender_id)] = {"step": "name"}
        await event.edit("➕ **ساخت پلن**\n\nنام پلن را ارسال کنید.", buttons=[[Button.inline("❌ لغو", PREFIX + b"cancel")]])
        await event.answer(); return
    if action == "cancel":
        _STATES.pop((get_tenant(), event.sender_id), None); await show(event); return
    if action.startswith("view:"):
        plan = await SERVICE.get(int(action.split(":", 1)[1]))
        if not plan: await event.answer("پلن پیدا نشد.", alert=True); return
        state = "🟢 فعال" if plan.enabled else "🔴 غیرفعال"
        await event.edit(f"📦 **{plan.name}**\n\n💾 حجم: `{plan.volume_gb:g} GB`\n⏱ مدت: `{plan.days}` روز\n💰 قیمت: `{plan.price:g}`\n📌 وضعیت: {state}", buttons=[[Button.inline("🔄 تغییر وضعیت", PREFIX + f"toggle:{plan.id}".encode())], [Button.inline("🗑 حذف", PREFIX + f"delete_prompt:{plan.id}".encode())], [Button.inline("🔙 لیست پلن‌ها", PREFIX + b"list")]])
        await event.answer(); return
    if action.startswith("toggle:"):
        await SERVICE.toggle(int(action.split(":", 1)[1])); await show(event); return
    if action.startswith("delete_prompt:"):
        plan = await SERVICE.get(int(action.split(":", 1)[1]))
        if not plan: await event.answer("پلن پیدا نشد.", alert=True); return
        await event.edit(f"⚠️ حذف پلن **{plan.name}** قطعی است. ادامه می‌دهید؟", buttons=[[Button.inline("✅ بله، حذف شود", PREFIX + f"delete:{plan.id}".encode())], [Button.inline("❌ انصراف", PREFIX + f"view:{plan.id}".encode())]])
        await event.answer(); return
    if action.startswith("delete:"):
        await SERVICE.delete(int(action.split(":", 1)[1])); await show(event); return
    await event.answer("گزینه نامعتبر است.", alert=True)


async def plan_text(event) -> None:
    if not await _owner(event) or not event.raw_text: return
    key = (get_tenant(), event.sender_id); state = _STATES.get(key)
    if not state: return
    text = event.raw_text.strip()
    if text in {"❌", "/cancel", "لغو"}:
        _STATES.pop(key, None); await event.respond("❌ عملیات لغو شد."); return
    try:
        step = state["step"]
        if step == "name":
            if not 2 <= len(text) <= 120: raise ValueError("نام باید بین 2 تا 120 کاراکتر باشد.")
            state.update(name=text, step="volume"); await event.respond("💾 حجم پلن را به GB وارد کنید. مثال: `0.5`"); return
        if step == "volume":
            value = float(text)
            if value <= 0: raise ValueError("حجم باید بیشتر از صفر باشد.")
            state.update(volume=value, step="days"); await event.respond("⏱ مدت پلن را به روز وارد کنید. مثال: `30`"); return
        if step == "days":
            value = int(text)
            if value <= 0: raise ValueError("مدت باید بیشتر از صفر باشد.")
            state.update(days=value, step="price"); await event.respond("💰 قیمت پلن را وارد کنید. عدد صفر هم مجاز است."); return
        if step == "price":
            value = float(text)
            if value < 0: raise ValueError("قیمت نمی‌تواند منفی باشد.")
            plan = await SERVICE.create(str(state["name"]), float(state["volume"]), int(state["days"]), value)
            _STATES.pop(key, None); await event.respond(f"✅ پلن **{plan.name}** با موفقیت ساخته شد."); return
    except (ValueError, TypeError) as exc:
        await event.respond(f"❌ ورودی نامعتبر: {exc}\n\nدوباره تلاش کنید یا `لغو` بفرستید.")

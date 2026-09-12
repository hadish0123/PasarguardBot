from __future__ import annotations

from telethon import Button, events
from app.core.ids import USER_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
from app.services.user_wallet import SERVICE
from app.services.representative_settings import SERVICE as SETTINGS
from app.services.orders import SERVICE as ORDERS
from app.services.representative_dashboard import RepresentativeDashboardService

PREFIX = b"user:wallet:"
ROOT_CALLBACK = b"user:wallet"
STATE: dict[tuple[str, int], dict] = {}
MIN_TOPUP = 5_000
MAX_TOPUP = 100_000_000


def _money(v: float) -> str:
    return f"{round(float(v)):,.0f} تومان"


def _digits(text: str) -> int:
    normalized = (text or "").replace(",", "").replace("٬", "").replace(" ", "").replace("تومان", "").strip()
    if not normalized.isdigit():
        raise ValueError("فقط مبلغ عددی وارد کنید.")
    return int(normalized)


async def allowed(event):
    if not event.is_private or not get_tenant():
        return False
    u = await USERS.get_by_telegram_id(event.sender_id)
    return bool(u and not u.blocked)


async def render_wallet(uid: int):
    balance = await SERVICE.balance(uid)
    transactions = await SERVICE.transactions(uid, 5)
    text = f"💳 **کیف پول من**\n\n💰 موجودی: **{_money(balance)}**\n"
    if transactions:
        text += "\n🧾 آخرین تراکنش‌ها:\n" + "\n".join(f"• {_money(float(t.amount))} — {t.reason}" for t in transactions)
    else:
        text += "\n🧾 هنوز تراکنشی ثبت نشده است."
    buttons = [
        [Button.inline("➕ شارژ کیف پول", PREFIX + b"topup")],
        [Button.inline("🧾 تاریخچه کامل", PREFIX + b"history"), Button.inline("🔄 بروزرسانی", PREFIX + b"show")],
        [Button.inline("🔙 فروشگاه", b"user:home")],
    ]
    return text, buttons


async def payment_card():
    settings = await SETTINGS.snapshot()
    card = settings.get("payment_card_number", "").strip()
    holder = settings.get("payment_card_holder", "").strip()
    if not card or not holder:
        return None, None
    return card, holder


async def render_callback(event):
    data = event.data or b""
    action = data[len(PREFIX):].decode(errors="ignore") if data.startswith(PREFIX) else "show"
    key = (get_tenant(), int(event.sender_id))
    state = STATE.setdefault(key, {})
    if action in ("", "show"):
        text, buttons = await render_wallet(event.sender_id)
        await event.edit(text, buttons=buttons)
        return
    if action == "topup":
        card, holder = await payment_card()
        if not card:
            await event.answer("⚠️ شماره کارت و نام صاحب کارت توسط مدیریت تنظیم نشده است.", alert=True)
            return
        state["awaiting_topup_amount"] = True
        await event.answer()
        return await event.edit(
            f"➕ **شارژ کیف پول**\n\nحداقل: **{_money(MIN_TOPUP)}**\nحداکثر: **{_money(MAX_TOPUP)}**\n\n💳 واریز فقط به کارت زیر انجام می‌شود:\n`{card}`\n👤 به نام: **{holder}**\n\nمبلغ دلخواه را به تومان ارسال کنید.",
            buttons=[[Button.inline("❌ لغو", PREFIX + b"cancel")]],
        )
    if action == "cancel":
        STATE.pop(key, None)
        text, buttons = await render_wallet(event.sender_id)
        return await event.edit(text, buttons=buttons)
    if action == "history":
        tx = await SERVICE.transactions(event.sender_id, 50)
        text = "🧾 **تاریخچه کیف پول**\n\n" + ("\n".join(f"• {_money(float(t.amount))} — {t.reason}" for t in tx) if tx else "هنوز تراکنشی ثبت نشده است.")
        return await event.edit(text, buttons=[[Button.inline("🔙 کیف پول", PREFIX + b"show")]])
    await event.answer("گزینه نامعتبر است.", alert=True)


async def _notify_owner(event, order, receipt_label, photo_file_id=None):
    try:
        owner_id = int((await RepresentativeDashboardService().snapshot())["owner_id"])
        caption = (f"🔔 شارژ کیف پول جدید\n\n🧾 سفارش: #{order.id}\n👤 کاربر: {order.telegram_user_id}\n"
                   f"💰 مبلغ: {_money(order.amount)}\n📎 {receipt_label}\n\nاز بخش «🛒 فروش و سفارش‌ها» پرداخت را تأیید یا لغو کنید.")
        if photo_file_id:
            await event.client._request("sendPhoto", {"chat_id": owner_id, "photo": photo_file_id, "caption": caption})
        else:
            await event.client.send_message(owner_id, caption)
    except Exception:
        pass


async def incoming(event, tenant_id):
    async with tenant_dispatch(tenant_id):
        if not await allowed(event):
            return
        key = (tenant_id, int(event.sender_id))
        state = STATE.get(key)
        if not state:
            return
        text = (event.raw_text or "").strip()
        if text.lower() in {"/cancel", "لغو"}:
            STATE.pop(key, None)
            return await event.respond("❌ عملیات لغو شد.")
        if state.get("awaiting_topup_amount"):
            try:
                amount = _digits(text)
                if amount < MIN_TOPUP or amount > MAX_TOPUP:
                    raise ValueError(f"مبلغ باید بین {_money(MIN_TOPUP)} تا {_money(MAX_TOPUP)} باشد.")
                order = await ORDERS.create_wallet_topup(event.sender_id, amount)
                state.clear()
                state["topup_order_id"] = order.id
                state["awaiting_topup_receipt"] = True
                card, holder = await payment_card()
                return await event.respond(
                    f"🧾 **درخواست شارژ #{order.id} ثبت شد**\n\n💰 مبلغ: **{_money(amount)}**\n💳 کارت مقصد: `{card}`\n👤 به نام: **{holder}**\n\nپس از واریز، تصویر رسید یا کد پیگیری را همینجا ارسال کنید.",
                    buttons=[[Button.inline("❌ لغو", PREFIX + b"cancel")]],
                )
            except (ValueError, LookupError) as exc:
                return await event.respond(f"❌ {exc}")
        if state.get("topup_order_id") and state.get("awaiting_topup_receipt"):
            order_id = int(state["topup_order_id"])
            try:
                photo_payload = (getattr(event, "_message_payload", {}) or {}).get("photo") or []
                if photo_payload:
                    file_id = photo_payload[-1].get("file_id")
                    if not file_id:
                        raise ValueError("شناسه تصویر رسید پیدا نشد.")
                    await ORDERS.submit_payment(order_id, f"photo:{file_id}")
                    label = "تصویر رسید"
                    photo = file_id
                else:
                    if not text:
                        return await event.respond("📎 تصویر رسید یا کد پیگیری را ارسال کنید.")
                    await ORDERS.submit_payment(order_id, text)
                    label = text[:80]
                    photo = None
                order = await ORDERS.get(order_id)
                await _notify_owner(event, order, label, photo)
                STATE.pop(key, None)
                return await event.respond(
                    f"✅ رسید شارژ **#{order_id}** دریافت شد.\n\n🕐 وضعیت: در انتظار تأیید مدیریت.",
                    buttons=[[Button.inline("💳 کیف پول", PREFIX + b"show")], [Button.inline("🏪 فروشگاه", b"user:home")]],
                )
            except (LookupError, ValueError) as exc:
                return await event.respond(f"❌ {exc}")


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await allowed(event):
                return await event.answer("دسترسی به این بخش را ندارید.", alert=True)
            await event.answer()
            await render_callback(event)

    client.add_event_handler(
        callback,
        events.CallbackQuery(func=lambda e: bool(e.data and (e.data == ROOT_CALLBACK or e.data.startswith(PREFIX)))),
    )

    async def msg(event):
        await incoming(event, tenant_id)

    client.add_event_handler(msg, events.NewMessage(incoming=True))

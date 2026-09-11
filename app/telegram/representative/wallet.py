from __future__ import annotations

from telethon import Button, events

from app.core.ids import USER_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
from app.services.user_wallet import SERVICE

PREFIX = b"user:wallet:"


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await allowed(event):
                return await event.answer("دسترسی به این بخش ندارید.", alert=True)
            await render_callback(event)
    client.add_event_handler(callback, events.CallbackQuery(data=PREFIX))


async def allowed(event):
    if not event.is_private or not get_tenant():
        return False
    user = await USERS.get_by_telegram_id(event.sender_id)
    return bool(user and not user.blocked)


def _amount(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.2f}"


async def render_wallet(telegram_user_id: int):
    balance = await SERVICE.balance(telegram_user_id)
    transactions = await SERVICE.transactions(telegram_user_id, 5)
    text = f"💳 **کیف پول من**\n\n💰 موجودی: **{balance:,.2f}**\n"
    if transactions:
        text += "\n🧾 آخرین تراکنش‌ها:\n"
        text += "\n".join(f"• {_amount(float(t.amount))} — {t.reason}" for t in transactions)
    else:
        text += "\n🧾 هنوز تراکنشی ثبت نشده است."
    buttons = [
        [Button.inline("🧾 تاریخچه کامل", PREFIX + b"history")],
        [Button.inline("🔄 بروزرسانی", PREFIX + b"show")],
        [Button.inline("🔙 فروشگاه", b"user:" + USER_HOME.encode())],
    ]
    return text, buttons


async def render_callback(event):
    action = event.data[len(PREFIX):].decode(errors="ignore")
    if action in ("", "show"):
        text, buttons = await render_wallet(event.sender_id)
        await event.edit(text, buttons=buttons)
        return await event.answer()

    if action == "history":
        transactions = await SERVICE.transactions(event.sender_id, 50)
        if not transactions:
            text = "🧾 **تاریخچه کیف پول**\n\nهنوز تراکنشی ثبت نشده است."
        else:
            text = "🧾 **تاریخچه کیف پول**\n\n" + "\n".join(
                f"• {_amount(float(t.amount))} — {t.reason}"
                for t in transactions
            )
        buttons = [[Button.inline("🔙 کیف پول", PREFIX + b"show")]]
        await event.edit(text, buttons=buttons)
        return await event.answer()

    await event.answer("گزینه نامعتبر است.", alert=True)

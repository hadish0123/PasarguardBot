from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from telethon import Button, events

from app.db.models import Order, ServiceSubscription
from app.db.session import SessionFactory
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE

PREFIX = b"rep:users:"
BACK = b"rep:home"
PAGE_SIZE = 8
_STATES: dict[tuple[str, int], dict] = {}


def _toman(value) -> int:
    return int(Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _key(event) -> tuple[str, int]:
    return get_tenant(), int(event.sender_id)


def register(client, tenant_id: str | None = None) -> None:
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            await callback_handler(event)

    async def message(event):
        async with tenant_dispatch(tenant_id):
            await message_handler(event)

    client.add_event_handler(callback, events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))))
    client.add_event_handler(message, events.NewMessage(incoming=True))


async def _authorized(event) -> bool:
    if not event.is_private or not get_tenant():
        return False
    from app.services.representative_dashboard import RepresentativeDashboardService
    return await RepresentativeDashboardService().is_owner(event.sender_id)


def _name(user) -> str:
    full = " ".join(x for x in (user.first_name, user.last_name) if x).strip()
    return full or (f"@{user.username}" if user.username else str(user.telegram_user_id))


def _status(user) -> str:
    return "🚫 مسدود" if user.blocked else "🟢 فعال"


def _user_text(user, services: int, orders: int) -> str:
    username = f"@{user.username}" if user.username else "—"
    return (
        "👤 **جزئیات کاربر**\n\n"
        f"🪪 نام: **{_name(user)}**\n"
        f"🔹 یوزرنیم: `{username}`\n"
        f"🆔 Telegram ID: `{user.telegram_user_id}`\n"
        f"💰 موجودی: **{_toman(user.balance):,} تومان**\n"
        f"📦 سرویس‌ها: **{services}**\n"
        f"🧾 سفارش‌ها: **{orders}**\n"
        f"📌 وضعیت: **{_status(user)}**\n\n"
        "عملیات موردنظر را انتخاب کنید:"
    )


async def render(query: str | None = None, page: int = 0):
    total = await SERVICE.count(query=query)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    users = await SERVICE.list(query=query, limit=PAGE_SIZE, offset=page * PAGE_SIZE)

    title = "👥 **مدیریت کاربران**"
    if query:
        title += f"\n🔎 جستجو: `{query}`"

    if not users:
        return title + "\n\n⚠️ کاربری مطابق جستجو پیدا نشد.", [
            [Button.inline("🔎 جستجوی دوباره", PREFIX + b"search")],
            [Button.inline("📋 نمایش همه کاربران", PREFIX + b"list:0")],
            [Button.inline("📊 داشبورد", BACK)],
        ]

    text = (
        f"{title}\n\n"
        f"👥 تعداد نتایج: **{total}**\n"
        f"📄 صفحه **{page + 1} از {pages}**\n\n"
        "برای مشاهده جزئیات، کاربر را انتخاب کنید:"
    )
    buttons = []
    for user in users:
        username = f" @{user.username}" if user.username else ""
        label = f"{_status(user)} {_name(user)[:22]}{username[:18]}"
        buttons.append([Button.inline(label[:60], PREFIX + f"view:{user.id}".encode())])

    nav = []
    if page > 0:
        nav.append(Button.inline("◀️ قبلی", PREFIX + f"list:{page - 1}".encode()))
    if page + 1 < pages:
        nav.append(Button.inline("بعدی ▶️", PREFIX + f"list:{page + 1}".encode()))
    if nav:
        buttons.append(nav)

    buttons += [
        [Button.inline("🔎 جستجو", PREFIX + b"search")],
        [Button.inline("🔄 بروزرسانی", PREFIX + f"list:{page}".encode())],
        [Button.inline("📊 داشبورد", BACK)],
    ]
    return text, buttons


async def _show_list(event, query: str | None = None, page: int = 0, respond: bool = False):
    text, buttons = await render(query, page)
    if respond:
        return await event.respond(text, buttons=buttons)
    return await event.edit(text, buttons=buttons)


async def _user_counts(telegram_user_id: int) -> tuple[int, int]:
    if SessionFactory is None:
        return 0, 0
    tenant_id = get_tenant()
    async with SessionFactory() as session:
        services = int((await session.scalar(select(func.count(ServiceSubscription.id)).where(
            ServiceSubscription.tenant_id == tenant_id,
            ServiceSubscription.telegram_user_id == telegram_user_id,
        ))) or 0)
        orders = int((await session.scalar(select(func.count(Order.id)).where(
            Order.tenant_id == tenant_id,
            Order.telegram_user_id == telegram_user_id,
        ))) or 0)
    return services, orders


async def _show_detail(event, user_id: int):
    user = await SERVICE.get(user_id)
    if user is None:
        return await event.answer("کاربر پیدا نشد.", alert=True)
    services, orders = await _user_counts(user.telegram_user_id)
    label = "✅ رفع مسدودی" if user.blocked else "🚫 مسدود کردن"
    buttons = [
        [Button.inline(label, PREFIX + f"toggle:{user.id}".encode())],
        [
            Button.inline("💰 افزایش موجودی", PREFIX + f"balance:{user.id}:add".encode()),
            Button.inline("💸 کاهش موجودی", PREFIX + f"balance:{user.id}:sub".encode()),
        ],
        [Button.inline("👥 بازگشت به کاربران", PREFIX + b"list:0")],
        [Button.inline("📊 داشبورد", BACK)],
    ]
    await event.edit(_user_text(user, services, orders), buttons=buttons)


async def _clear_prompt(event, state: dict):
    message_id = state.get("prompt_message_id")
    if not message_id:
        return
    try:
        await event.client.delete_messages(event.chat_id, message_id)
    except Exception:
        pass


async def callback_handler(event):
    if not await _authorized(event):
        return await event.answer("دسترسی مدیریت ندارید.", alert=True)

    raw = event.data[len(PREFIX):].decode(errors="ignore")

    if raw.startswith("list:"):
        try:
            page = max(0, int(raw.split(":", 1)[1]))
        except ValueError:
            page = 0
        _STATES.pop(_key(event), None)
        await _show_list(event, page=page)
        return await event.answer()

    if raw == "search":
        key = _key(event)
        state = {"step": "search"}
        prompt = await event.respond(
            "🔎 **جستجوی کاربر**\n\n"
            "Telegram ID، یوزرنیم یا نام را ارسال کنید.\n\n"
            "مثال: `8683775407`\n\n"
            "برای لغو دکمه زیر را بزنید:",
            buttons=[[Button.inline("❌ لغو", PREFIX + b"cancel")]],
        )
        state["prompt_message_id"] = prompt.get("message_id") if isinstance(prompt, dict) else getattr(prompt, "id", None)
        _STATES[key] = state
        return await event.answer()

    if raw == "cancel":
        _STATES.pop(_key(event), None)
        return await _show_list(event, page=0)

    if raw.startswith("view:"):
        try:
            user_id = int(raw.split(":", 1)[1])
        except ValueError:
            return await event.answer("شناسه کاربر نامعتبر است.", alert=True)
        _STATES.pop(_key(event), None)
        await _show_detail(event, user_id)
        return await event.answer()

    if raw.startswith("toggle:"):
        try:
            user = await SERVICE.toggle_block(int(raw.split(":", 1)[1]))
            await _show_detail(event, user.id)
            return await event.answer("وضعیت کاربر به‌روزرسانی شد.")
        except Exception as exc:
            return await event.answer(f"❌ عملیات انجام نشد: {str(exc)[:100]}", alert=True)

    if raw.startswith("balance:"):
        try:
            _, user_id, direction = raw.split(":")
            user_id = int(user_id)
            if direction not in {"add", "sub"}:
                raise ValueError
        except ValueError:
            return await event.answer("عملیات موجودی نامعتبر است.", alert=True)
        label = "افزایش" if direction == "add" else "کاهش"
        _STATES[_key(event)] = {"step": "balance", "user_id": user_id, "direction": direction}
        await event.edit(
            f"💰 **{label} موجودی کاربر**\n\n"
            "مبلغ را فقط به تومان و به‌صورت عدد صحیح ارسال کنید.\n"
            "مثال: `100000`\n\n"
            "لغو: «لغو»",
            buttons=[[Button.inline("❌ لغو", PREFIX + f"view:{user_id}".encode())]],
        )
        return await event.answer()

    await event.answer("گزینه نامعتبر است.", alert=True)


async def message_handler(event):
    if not await _authorized(event):
        return
    key = _key(event)
    state = _STATES.get(key)
    if not state:
        return

    text = (event.raw_text or "").strip()
    if text.lower() in {"لغو", "/cancel", "❌"}:
        _STATES.pop(key, None)
        await _show_list(event, page=0, respond=True)
        return

    if state["step"] == "search":
        _STATES.pop(key, None)
        await _clear_prompt(event, state)
        text_out, buttons = await render(text, 0)
        await event.respond(text_out, buttons=buttons)
        return

    if state["step"] == "balance":
        try:
            amount = _toman(text.replace(",", "").replace("٬", ""))
        except (ValueError, TypeError):
            await event.respond("❌ مبلغ نامعتبر است. فقط عدد صحیح تومان وارد کنید.")
            return
        if amount <= 0:
            await event.respond("❌ مبلغ باید بزرگ‌تر از صفر باشد.")
            return
        signed = amount if state["direction"] == "add" else -amount
        try:
            user = await SERVICE.adjust_balance(state["user_id"], signed, "تغییر موجودی توسط نماینده", event.sender_id)
        except (ValueError, LookupError) as exc:
            await event.respond(f"❌ {exc}")
            return
        except Exception:
            await event.respond("❌ تغییر موجودی انجام نشد. دوباره تلاش کنید.")
            return
        _STATES.pop(key, None)
        await event.respond(
            "✅ **عملیات موجودی با موفقیت انجام شد.**\n\n"
            f"👤 کاربر: **{_name(user)}**\n"
            f"💰 موجودی جدید: **{_toman(user.balance):,} تومان**",
            buttons=[
                [Button.inline("👤 مشاهده کاربر", PREFIX + f"view:{user.id}".encode())],
                [Button.inline("👥 مدیریت کاربران", PREFIX + b"list:0")],
            ],
        )

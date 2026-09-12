from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from telethon import Button, events
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE

PREFIX = b"rep:users:"
BACK = b"rep:rep.home"
_STATES: dict[tuple[str, int], dict] = {}


def _toman(value) -> int:
    """Render all representative-panel money as whole Toman."""
    return int(Decimal(str(value or 0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def register(client, tenant_id: str | None = None) -> None:
    async def callback(event):
        async with tenant_dispatch(tenant_id): await callback_handler(event)
    async def message(event):
        async with tenant_dispatch(tenant_id): await message_handler(event)
    client.add_event_handler(callback, events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))))
    client.add_event_handler(message, events.NewMessage(incoming=True))


async def _authorized(event) -> bool:
    if not event.is_private or not get_tenant(): return False
    from app.services.representative_dashboard import RepresentativeDashboardService
    return await RepresentativeDashboardService().is_owner(event.sender_id)


def _name(user) -> str:
    full = " ".join(x for x in (user.first_name, user.last_name) if x).strip()
    return full or (f"@{user.username}" if user.username else str(user.telegram_user_id))


def _user_text(user) -> str:
    status = "🚫 مسدود" if user.blocked else "🟢 فعال"
    username = f"@{user.username}" if user.username else "—"
    balance = _toman(user.balance)
    return (f"👤 **جزئیات کاربر**\n\n" f"نام: **{_name(user)}**\n" f"یوزرنیم: `{username}`\n" f"Telegram ID: `{user.telegram_user_id}`\n" f"💰 موجودی: **{balance:,} تومان**\n" f"وضعیت: **{status}**\n\n" "از دکمه‌های زیر برای مدیریت همین کاربر استفاده کنید.")


async def render(query: str | None = None):
    users = await SERVICE.list(query=query); title = "👥 **مدیریت کاربران**"
    if query: title += f"\n🔎 جستجو: `{query}`"
    if not users: return title + "\n\nکاربری با این مشخصات پیدا نشد.", [[Button.inline("🔎 جستجوی کاربر", PREFIX+b"search")],[Button.inline("📊 داشبورد",BACK)]]
    buttons=[]
    for user in users:
        status="🚫" if user.blocked else "🟢"; buttons.append([Button.inline(f"{status} {_name(user)[:28]}",PREFIX+f"view:{user.id}".encode())])
    buttons += [[Button.inline("🔎 جستجو",PREFIX+b"search")],[Button.inline("📊 داشبورد",BACK)]]
    return title+f"\n\nتعداد نمایش: **{len(users)}**",buttons


async def _show_list(event, query: str | None = None):
    text,buttons=await render(query); await event.edit(text,buttons=buttons)


async def _show_detail(event,user_id:int):
    user=await SERVICE.get(user_id)
    if user is None: return await event.answer("کاربر پیدا نشد.",alert=True)
    label="✅ رفع مسدودی" if user.blocked else "🚫 مسدود کردن"
    buttons=[[Button.inline(label,PREFIX+f"toggle:{user.id}".encode())],[Button.inline("💰 افزایش موجودی",PREFIX+f"balance:{user.id}:add".encode()),Button.inline("💸 کاهش موجودی",PREFIX+f"balance:{user.id}:sub".encode())],[Button.inline("👥 بازگشت به کاربران",PREFIX+b"list")],[Button.inline("📊 داشبورد",BACK)]]
    await event.edit(_user_text(user),buttons=buttons)


async def callback_handler(event):
    if not await _authorized(event): return await event.answer("دسترسی مدیریت ندارید.",alert=True)
    raw=event.data[len(PREFIX):].decode(errors="ignore")
    if raw=="list": await _show_list(event); return await event.answer()
    if raw=="search":
        _STATES[(get_tenant(),event.sender_id)]={"step":"search"}; await event.edit("🔎 **جستجوی کاربر**\n\nTelegram ID، یوزرنیم یا نام را ارسال کنید.\n\nبرای لغو: `لغو`",buttons=[[Button.inline("❌ لغو",PREFIX+b"list")]]); return await event.answer()
    if raw.startswith("view:"): await _show_detail(event,int(raw.split(":",1)[1])); return await event.answer()
    if raw.startswith("toggle:"):
        user=await SERVICE.toggle_block(int(raw.split(":",1)[1])); await _show_detail(event,user.id); return await event.answer("وضعیت کاربر به‌روزرسانی شد.")
    if raw.startswith("balance:"):
        _,user_id,direction=raw.split(":"); _STATES[(get_tenant(),event.sender_id)]={"step":"balance","user_id":int(user_id),"direction":direction}; label="افزایش" if direction=="add" else "کاهش"; await event.edit(f"💰 **{label} موجودی**\n\nمبلغ را به‌صورت عدد ارسال کنید.\nمثال: `100000`\n\nبرای لغو: `لغو`",buttons=[[Button.inline("❌ لغو",PREFIX+f"view:{user_id}".encode())]]); return await event.answer()
    await event.answer("گزینه نامعتبر است.",alert=True)


async def message_handler(event):
    if not await _authorized(event): return
    state=_STATES.get((get_tenant(),event.sender_id))
    if not state: return
    text=(event.raw_text or "").strip(); key=(get_tenant(),event.sender_id)
    if text.lower() in {"لغو","/cancel","❌"}:
        _STATES.pop(key,None); text_out,buttons=await render(); await event.respond(text_out,buttons=buttons); return
    if state["step"]=="search":
        _STATES.pop(key,None); text_out,buttons=await render(text); await event.respond(text_out,buttons=buttons); return
    if state["step"]=="balance":
        try: amount=_toman(text.replace(",",""))
        except (ValueError, TypeError): await event.respond("❌ مبلغ نامعتبر است. فقط عدد وارد کنید."); return
        if amount<=0: await event.respond("❌ مبلغ باید بزرگ‌تر از صفر باشد."); return
        signed=amount if state["direction"]=="add" else -amount
        try: user=await SERVICE.adjust_balance(state["user_id"],signed,"تغییر موجودی توسط نماینده",event.sender_id)
        except ValueError as exc: await event.respond(f"❌ {exc}"); return
        _STATES.pop(key,None); await event.respond(f"✅ موجودی با موفقیت تغییر کرد.\n\nموجودی جدید: **{_toman(user.balance):,} تومان**",buttons=[[Button.inline("👤 مشاهده کاربر",PREFIX+f"view:{user.id}".encode())],[Button.inline("👥 کاربران",PREFIX+b"list")]])

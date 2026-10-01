from __future__ import annotations

from telethon import Button, events

from app.core.ids import REP_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.panel_status import SERVICE
from app.services.representative_dashboard import RepresentativeDashboardService

PREFIX = b"rep:panel:"
INPUTS: dict[tuple[str, int], str] = {}


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await _authorized(event):
                return await event.answer("دسترسی مدیریت ندارید.", alert=True)
            await handle(event)

    async def message(event):
        async with tenant_dispatch(tenant_id):
            if not await _authorized(event):
                return

            key = (get_tenant(), event.sender_id)
            field = INPUTS.get(key)
            if not field:
                return

            value = (event.raw_text or "").strip()
            if value.lower() in {"/cancel", "cancel"} or value == "لغو":
                INPUTS.pop(key, None)
                text, buttons = await render()
                return await event.respond("❌ تغییر لغو شد.\n\n" + text, buttons=buttons, parse_mode=None)

            try:
                status = await SERVICE.update_field(field, value, actor_id=event.sender_id)
            except ValueError as exc:
                return await event.respond(f"❌ {exc}\n\nمقدار درست را ارسال کنید یا /cancel بزنید.", parse_mode=None)
            except Exception:
                return await event.respond("❌ ذخیره تنظیمات انجام نشد. دوباره تلاش کنید یا /cancel بزنید.", parse_mode=None)

            INPUTS.pop(key, None)
            text, buttons = await saved_result(field, status)
            await event.respond(text, buttons=buttons, parse_mode=None)

    client.add_event_handler(
        callback,
        events.CallbackQuery(
            func=lambda e: bool(e.data and (e.data.startswith(PREFIX) or e.data == b"rep:panel"))
        ),
    )
    client.add_event_handler(message, events.NewMessage(incoming=True))


async def _authorized(event):
    return bool(
        event.is_private
        and get_tenant()
        and await RepresentativeDashboardService().is_owner(event.sender_id)
    )


async def render(status=None):
    if status is None:
        status = await SERVICE.snapshot()
    icons = {
        "connected": "🟢 متصل",
        "unreachable": "🔴 قطع / غیرقابل دسترس",
        "unauthorized": "🟠 احراز هویت ناموفق",
        "missing": "⚪ پیکربندی ناقص",
        "unknown": "⚪ تست نشده",
    }
    state = icons.get(status.state, "⚠️ خطا")
    url = status.panel_url or "ثبت نشده"
    username = status.panel_username or "ثبت نشده"
    text = (
        "🔌 وضعیت اتصال پنل پاسارگارد\n\n"
        f"📡 وضعیت اتصال: {state}\n"
        f"🌐 آدرس پنل: {url}\n"
        f"👤 کاربر پنل: {username}\n"
        f"🏷 وضعیت نماینده: {status.tenant_status}\n\n"
        f"ℹ️ {status.message}\n\n"
        "🔐 API Key به‌صورت امن ذخیره شده و در این صفحه نمایش داده نمی‌شود."
    )
    buttons = [
        [Button.inline("✏️ تغییر اتصال", PREFIX + b"edit")],
        [Button.inline("🔄 تست اتصال", PREFIX + b"check")],
        [Button.inline("📋 نمایش دوباره", PREFIX + b"list")],
        [Button.inline("📊 داشبورد", b"rep:" + REP_HOME.encode())],
    ]
    return text, buttons


async def saved_result(field, status):
    labels = {
        "panel_url": "لینک ورود پنل",
        "panel_username": "یوزرنیم پنل",
        "panel_api_key": "API Key پنل",
    }
    states = {
        "connected": ("🟢", "اتصال با موفقیت برقرار شد."),
        "unauthorized": ("🟠", "اتصال برقرار شد اما احراز هویت ناموفق است؛ API Key را بررسی کنید."),
        "unreachable": ("🔴", "پنل در تست اتصال پاسخ معتبر نداد یا در دسترس نبود."),
        "missing": ("⚪", "اطلاعات اتصال هنوز کامل نیست."),
        "unknown": ("⚪", "وضعیت اتصال مشخص نشد."),
    }
    icon, result = states.get(status.state, ("⚠️", status.message))
    label = labels.get(field, "تنظیمات اتصال")
    text = (
        f"✅ {label} با موفقیت ثبت شد.\n\n"
        "🔄 تست اتصال خودکار انجام شد\n"
        f"{icon} {result}\n\n"
        f"🌐 آدرس پنل: {status.panel_url or 'ثبت نشده'}\n"
        f"👤 یوزرنیم: {status.panel_username or 'ثبت نشده'}\n\n"
        "🔐 API Key نمایش داده نمی‌شود."
    )
    buttons = [
        [Button.inline("🔙 بازگشت", PREFIX + b"edit")],
        [Button.inline("🔄 تست دوباره", PREFIX + b"check")],
        [Button.inline("📊 داشبورد", b"rep:" + REP_HOME.encode())],
    ]
    return text, buttons


async def edit_menu():
    status = await SERVICE.snapshot()
    url = status.panel_url or "ثبت نشده"
    username = status.panel_username or "ثبت نشده"
    text = (
        "✏️ تغییر اتصال پاسارگارد\n\n"
        "هر مورد جداگانه تغییر می‌کند؛ موارد دیگر دست‌نخورده می‌مانند.\n\n"
        f"🌐 آدرس فعلی: {url}\n"
        f"👤 یوزرنیم فعلی: {username}\n"
        "🔐 API Key فعلی به دلایل امنیتی نمایش داده نمی‌شود.\n\n"
        "موردی را که می‌خواهید تغییر دهید انتخاب کنید."
    )
    buttons = [
        [Button.inline("🌐 تغییر لینک ورود", PREFIX + b"edit:panel_url")],
        [Button.inline("👤 تغییر یوزرنیم", PREFIX + b"edit:panel_username")],
        [Button.inline("🔐 تغییر API Key", PREFIX + b"edit:panel_api_key")],
        [Button.inline("🔙 وضعیت اتصال", PREFIX + b"list")],
    ]
    return text, buttons


async def handle(event):
    action = event.data[len(PREFIX):].decode(errors="ignore") if event.data.startswith(PREFIX) else "list"
    key = (get_tenant(), event.sender_id)

    if action == "check":
        INPUTS.pop(key, None)
        await event.edit("⏳ در حال بررسی اتصال به پنل پاسارگارد...", buttons=[], parse_mode=None)
        status = await SERVICE.check()
        text, buttons = await render(status)
        await event.edit(text, buttons=buttons, parse_mode=None)
        return await event.answer("اتصال برقرار است." if status.state == "connected" else "نتیجه تست اتصال نمایش داده شد.")

    if action == "edit":
        INPUTS.pop(key, None)
        text, buttons = await edit_menu()
        await event.edit(text, buttons=buttons, parse_mode=None)
        return await event.answer()

    if action.startswith("edit:"):
        field = action[5:]
        prompts = {
            "panel_url": (
                "🌐 تغییر لینک ورود پنل\n\n"
                "آدرس جدید پنل را ارسال کنید.\n"
                "مثال: https://panel.example.com\n\n"
                "فقط لینک پنل تغییر می‌کند؛ یوزرنیم و API Key دست‌نخورده می‌مانند."
            ),
            "panel_username": (
                "👤 تغییر یوزرنیم پنل\n\n"
                "یوزرنیم جدید را ارسال کنید.\n\n"
                "فقط یوزرنیم تغییر می‌کند؛ لینک پنل و API Key دست‌نخورده می‌مانند."
            ),
            "panel_api_key": (
                "🔐 تغییر API Key پنل\n\n"
                "API Key جدید را ارسال کنید.\n\n"
                "فقط API Key تغییر می‌کند؛ لینک پنل و یوزرنیم دست‌نخورده می‌مانند.\n"
                "کلید جدید رمزنگاری می‌شود و بعداً نمایش داده نخواهد شد."
            ),
        }
        if field not in prompts:
            return await event.answer("گزینه نامعتبر است.", alert=True)
        INPUTS[key] = field
        return await event.edit(
            prompts[field] + "\n\nبرای لغو /cancel را ارسال کنید.",
            buttons=[[Button.inline("❌ لغو", PREFIX + b"edit")]],
            parse_mode=None,
        )

    if action in ("list", ""):
        INPUTS.pop(key, None)
        text, buttons = await render()
        await event.edit(text, buttons=buttons, parse_mode=None)
        return await event.answer()

    return await event.answer("گزینه نامعتبر است.", alert=True)

from __future__ import annotations

from telethon import Button, events

from app.db.models import RegistrationStatus
from app.services.registration_store import RegistrationStore
from app.telegram.central.registration import register_registration_handlers


STORE = RegistrationStore()
CANCEL = b"central:cancel"
HOME = b"central:home"
TRACK_INPUT = b"central:track:input"
TRACK_LATEST = b"central:track:latest"


def menu():
    return [
        [Button.inline("🤖 ثبت ربات نمایندگی", b"central:register")],
        [Button.inline("🔎 پیگیری درخواست", TRACK_INPUT)],
    ]


def back_button():
    return [[Button.inline("🔙 بازگشت", HOME)]]


def register_central_handlers(client) -> None:
    client.add_event_handler(start, events.NewMessage(pattern=r"^/start$"))
    client.add_event_handler(text_router, events.NewMessage(incoming=True))
    client.add_event_handler(register, events.CallbackQuery(data=b"central:register"))
    client.add_event_handler(track_input, events.CallbackQuery(data=TRACK_INPUT))
    client.add_event_handler(track_latest, events.CallbackQuery(data=TRACK_LATEST))
    client.add_event_handler(home, events.CallbackQuery(data=HOME))
    client.add_event_handler(cancel, events.CallbackQuery(data=CANCEL))
    register_registration_handlers(client)


def _private(event) -> bool:
    return bool(event.is_private)


async def start(event):
    if not _private(event):
        return
    await event.respond(home_text(), buttons=menu())


async def home(event):
    if not _private(event):
        return
    await event.answer()
    await event.edit(home_text(), buttons=menu())


async def register(event):
    if not _private(event):
        return
    await event.answer()
    try:
        record = await STORE.create_or_resume_draft(event.sender_id)
    except Exception:
        await event.edit(
            "❌ در ایجاد درخواست مشکلی پیش آمد.\n\nلطفاً چند لحظه بعد دوباره تلاش کنید.",
            buttons=back_button(),
        )
        return

    if record.status != RegistrationStatus.DRAFT.value:
        await event.edit(registration_status_text(record), buttons=[[Button.inline("🔙 بازگشت", HOME)]])
        return

    await event.edit(
        "🤖 **ثبت ربات نمایندگی**\n\n"
        "درخواست شما ایجاد یا ادامه داده شد.\n\n"
        f"🆔 کد پیگیری: `{record.tracking_code}`\n\n"
        "اطلاعات ربات و پنل را مرحله‌به‌مرحله وارد می‌کنید.",
        buttons=[
            [Button.inline("▶️ ادامه ثبت", b"central:registration:continue")],
            [Button.inline("🔎 مشاهده وضعیت", TRACK_LATEST)],
            [Button.inline("🔙 بازگشت", HOME)],
        ],
    )


async def track_input(event):
    if not _private(event):
        return
    await event.answer()
    await event.edit(
        "🔎 **پیگیری درخواست**\n\nکد پیگیری را ارسال کنید.\nمثال: `PG-A1B2C3D4`",
        buttons=[[Button.inline("❌ لغو", CANCEL)]],
    )


async def track_latest(event):
    if not _private(event):
        return
    await event.answer()
    try:
        record = await STORE.latest_for_owner(event.sender_id)
    except Exception:
        await event.edit("❌ دریافت وضعیت درخواست ممکن نشد.\n\nلطفاً دوباره تلاش کنید.", buttons=back_button())
        return
    if record is None:
        await event.edit("📭 هنوز هیچ درخواست نمایندگی برای حساب شما ثبت نشده است.", buttons=menu())
        return
    await event.edit(registration_status_text(record), buttons=menu())


async def text_router(event):
    if not _private(event) or not event.raw_text:
        return
    text = event.raw_text.strip()
    if text.lower() == "/start":
        return
    if text.lower() in {"لغو", "/cancel", "cancel"}:
        await event.respond(home_text(), buttons=menu())
        return
    if text.upper().startswith("PG-"):
        try:
            record = await STORE.get_by_tracking_code(event.sender_id, text.upper())
        except Exception:
            await event.respond("❌ پیگیری درخواست در حال حاضر در دسترس نیست.", buttons=menu())
            return
        if record is None:
            await event.respond("❌ کد پیگیری پیدا نشد.\n\nکد را دقیقاً مانند نمونه ارسال کنید یا از منوی اصلی دوباره تلاش کنید.", buttons=menu())
            return
        await event.respond(registration_status_text(record), buttons=menu())


async def cancel(event):
    if not _private(event):
        return
    await event.answer()
    await event.edit(home_text(), buttons=menu())


def home_text() -> str:
    return (
        "🌐 **سامانه مرکزی نمایندگان**\n\n"
        "از این بخش می‌توانید ربات نمایندگی خود را ثبت کنید و وضعیت درخواست را پیگیری کنید.\n\n"
        "🔐 اطلاعات هر نماینده به‌صورت مستقل مدیریت می‌شود."
    )


def registration_status_text(record) -> str:
    labels = {
        RegistrationStatus.DRAFT.value: "📝 پیش‌نویس — ثبت اطلاعات هنوز کامل نشده است.",
        RegistrationStatus.PENDING.value: "⏳ در انتظار بررسی — درخواست ثبت شده و منتظر تأیید است.",
        RegistrationStatus.PROVISIONING.value: "⚙️ در حال راه‌اندازی — منابع ربات نمایندگی در حال آماده‌سازی است.",
        RegistrationStatus.ACTIVE.value: "✅ فعال — ربات نمایندگی شما فعال شده است.",
        RegistrationStatus.REJECTED.value: "❌ رد شده — درخواست نیاز به اصلاح یا ثبت مجدد دارد.",
    }
    reason = f"\n\n📌 دلیل: {record.rejection_reason}" if record.rejection_reason else ""
    brand = f"\n🏷 برند: {record.brand}" if record.brand else ""
    return "🔎 **وضعیت درخواست نمایندگی**\n\n" f"🆔 کد: `{record.tracking_code}`{brand}\n" f"\n{labels.get(record.status, '❔ وضعیت نامشخص')}{reason}"

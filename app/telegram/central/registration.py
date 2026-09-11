from __future__ import annotations

from telethon import Button, events

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.db.models import RegistrationStep, RegistrationStatus, RepresentativeRegistration
from app.db.session import SessionFactory
from app.services.pasarguard import PasarguardClient
from app.services.registration import RegistrationService
from app.services.registration_store import RegistrationStore
from app.services.secrets import secret_box
from app.services.telegram_bot import TelegramBotVerifier


STORE = RegistrationStore()
BOT_VERIFIER = TelegramBotVerifier()

CANCEL = b"central:registration:cancel"
CONTINUE = b"central:registration:continue"
CONFIRM = b"central:registration:confirm"
BACK = b"central:registration:back"

PROMPTS = {
    RegistrationStep.BRAND: "🏷 **مرحله ۱ از ۶ — نام برند**\n\nنام برند نمایندگی را ارسال کنید.",
    RegistrationStep.BOT_TOKEN: "🤖 **مرحله ۲ از ۶ — Bot Token**\n\nتوکن ربات نمایندگی را ارسال کنید.",
    RegistrationStep.BOT_ID: "🆔 **مرحله ۳ از ۶ — Bot ID**\n\nشناسه عددی ربات را ارسال کنید.",
    RegistrationStep.PANEL_URL: "🌐 **مرحله ۴ از ۶ — آدرس پنل**\n\nآدرس اصلی پنل پاسارگارد را ارسال کنید.\nمثال: `https://panel.example.com`",
    RegistrationStep.PANEL_USERNAME: "👤 **مرحله ۵ از ۶ — نام کاربری پنل**\n\nنام کاربری پنل پاسارگارد را ارسال کنید.",
    RegistrationStep.PANEL_API_KEY: "🔐 **مرحله ۶ از ۶ — API Key**\n\nAPI Key پنل پاسارگارد را ارسال کنید. این مقدار ذخیره‌شده رمزنگاری می‌شود.",
}


def register_registration_handlers(client) -> None:
    client.add_event_handler(continue_registration, events.CallbackQuery(data=CONTINUE))
    client.add_event_handler(cancel_registration, events.CallbackQuery(data=CANCEL))
    client.add_event_handler(confirm_registration, events.CallbackQuery(data=CONFIRM))
    client.add_event_handler(back_registration, events.CallbackQuery(data=BACK))
    client.add_event_handler(input_router, events.NewMessage(incoming=True))


def _private(event) -> bool:
    return bool(event.is_private)


async def continue_registration(event):
    if not _private(event):
        return
    await event.answer()
    record = await STORE.latest_for_owner(event.sender_id)
    if record is None:
        await event.edit("❌ درخواست ثبت پیدا نشد. از منوی اصلی دوباره شروع کنید.")
        return
    if record.status != RegistrationStatus.DRAFT.value:
        await event.edit("ℹ️ این درخواست دیگر در مرحله ورود اطلاعات نیست.")
        return
    await event.edit(PROMPTS[RegistrationStep(record.step)], buttons=wizard_buttons())


async def input_router(event):
    if not _private(event) or not event.raw_text:
        return
    if event.raw_text.strip().lower() in {"/cancel", "cancel", "لغو"}:
        return

    record = await STORE.latest_for_owner(event.sender_id)
    if record is None or record.status != RegistrationStatus.DRAFT.value:
        return
    step = RegistrationStep(record.step)
    value = event.raw_text.strip()
    try:
        next_step, message = await process_step(record, step, value)
    except ValidationError as exc:
        await event.respond(f"❌ {exc}\n\n{PROMPTS[step]}", buttons=wizard_buttons())
        return
    except Exception:
        await event.respond("❌ پردازش اطلاعات انجام نشد. دوباره تلاش کنید.", buttons=wizard_buttons())
        return

    if next_step == RegistrationStep.REVIEW:
        record = await STORE.latest_for_owner(event.sender_id)
        await event.respond(review_text(record), buttons=review_buttons())
        return
    await event.respond(message or PROMPTS[next_step], buttons=wizard_buttons())


async def process_step(record: RepresentativeRegistration, step: RegistrationStep, value: str) -> tuple[RegistrationStep, str | None]:
    if step == RegistrationStep.BRAND:
        brand = RegistrationService.validate_brand(value)
        await STORE.update(record.id, brand=brand, step=RegistrationStep.BOT_TOKEN.value)
        return RegistrationStep.BOT_TOKEN, None

    if step == RegistrationStep.BOT_TOKEN:
        bot = await BOT_VERIFIER.get_me(value)
        await STORE.update(
            record.id,
            bot_id=int(bot["id"]),
            bot_token_encrypted=secret_box.encrypt(value),
            step=RegistrationStep.BOT_ID.value,
        )
        username = bot.get("username") or "بدون نام کاربری"
        return RegistrationStep.BOT_ID, f"✅ ربات `@{username}` شناسایی شد.\n\n{PROMPTS[RegistrationStep.BOT_ID]}"

    if step == RegistrationStep.BOT_ID:
        if not value.isdigit():
            raise ValidationError("Bot ID باید فقط عدد باشد.")
        if record.bot_id != int(value):
            raise ValidationError("Bot ID با Bot Token مطابقت ندارد.")
        await STORE.set_step(record.id, RegistrationStep.PANEL_URL)
        return RegistrationStep.PANEL_URL, None

    if step == RegistrationStep.PANEL_URL:
        url = RegistrationService.normalize_panel_url(value)
        await STORE.update(record.id, panel_url=url, step=RegistrationStep.PANEL_USERNAME.value)
        return RegistrationStep.PANEL_USERNAME, None

    if step == RegistrationStep.PANEL_USERNAME:
        if not 2 <= len(value) <= 190 or " " in value:
            raise ValidationError("نام کاربری پنل معتبر نیست.")
        await STORE.update(record.id, panel_username=value, step=RegistrationStep.PANEL_API_KEY.value)
        return RegistrationStep.PANEL_API_KEY, None

    if step == RegistrationStep.PANEL_API_KEY:
        if len(value) < 8:
            raise ValidationError("API Key خیلی کوتاه است.")
        if not record.panel_url:
            raise ValidationError("آدرس پنل ثبت نشده است.")
        client = PasarguardClient(record.panel_url, value)
        if not await client.health():
            raise ValidationError("اتصال به پنل یا API Key معتبر نیست.")
        await STORE.update(record.id, panel_api_key_encrypted=secret_box.encrypt(value), step=RegistrationStep.REVIEW.value)
        return RegistrationStep.REVIEW, None

    raise ValidationError("مرحله ثبت نام نامعتبر است. از منوی اصلی دوباره شروع کنید.")


async def confirm_registration(event):
    if not _private(event):
        return
    await event.answer()
    record = await STORE.latest_for_owner(event.sender_id)
    if record is None or record.status != RegistrationStatus.DRAFT.value:
        await event.edit("❌ درخواست قابل تأیید نیست.")
        return
    required = (
        record.brand,
        record.bot_id,
        record.bot_token_encrypted,
        record.panel_url,
        record.panel_username,
        record.panel_api_key_encrypted,
    )
    if not all(required):
        await event.edit("❌ اطلاعات ناقص است. به مراحل ثبت برگردید.", buttons=wizard_buttons())
        return
    await STORE.mark_pending(record.id)
    for admin_id in settings.admin_ids:
        try:
            await event.client.send_message(admin_id, admin_notification(record))
        except Exception:
            continue
    await event.edit(
        "✅ **درخواست ثبت شد**\n\n"
        f"🆔 کد پیگیری: `{record.tracking_code}`\n\n"
        "درخواست برای بررسی ارسال شد. وضعیت را از منوی اصلی پیگیری کنید.",
        buttons=[[Button.inline("🔎 مشاهده وضعیت", b"central:track:latest")]],
    )


async def cancel_registration(event):
    if not _private(event):
        return
    await event.answer()
    await event.edit("❌ فرایند ثبت متوقف شد. برای ادامه، از منوی اصلی دوباره ثبت نمایندگی را انتخاب کنید.")


async def back_registration(event):
    if not _private(event):
        return
    await event.answer()
    record = await STORE.latest_for_owner(event.sender_id)
    if record is None or record.status != RegistrationStatus.DRAFT.value:
        return
    previous = {
        RegistrationStep.BOT_TOKEN: RegistrationStep.BRAND,
        RegistrationStep.BOT_ID: RegistrationStep.BOT_TOKEN,
        RegistrationStep.PANEL_URL: RegistrationStep.BOT_ID,
        RegistrationStep.PANEL_USERNAME: RegistrationStep.PANEL_URL,
        RegistrationStep.PANEL_API_KEY: RegistrationStep.PANEL_USERNAME,
        RegistrationStep.REVIEW: RegistrationStep.PANEL_API_KEY,
    }.get(RegistrationStep(record.step))
    if previous is None:
        await event.edit(PROMPTS[RegistrationStep.BRAND], buttons=wizard_buttons())
        return
    await STORE.set_step(record.id, previous)
    await event.edit(PROMPTS[previous], buttons=wizard_buttons())


def wizard_buttons():
    return [[Button.inline("🔙 مرحله قبل", BACK), Button.inline("❌ لغو", CANCEL)]]


def review_buttons():
    return [
        [Button.inline("✅ تأیید و ارسال", CONFIRM)],
        [Button.inline("🔙 اصلاح اطلاعات", BACK), Button.inline("❌ لغو", CANCEL)],
    ]


def review_text(record) -> str:
    return (
        "📋 **بازبینی نهایی درخواست**\n\n"
        f"🏷 برند: {record.brand}\n"
        f"🤖 Bot ID: `{record.bot_id}`\n"
        f"🌐 پنل: `{record.panel_url}`\n"
        f"👤 نام کاربری پنل: `{record.panel_username}`\n"
        "🔐 API Key: `••••••••`\n\n"
        "اگر اطلاعات درست است، ارسال نهایی را بزنید."
    )


def admin_notification(record) -> str:
    return (
        "🔔 **درخواست جدید نمایندگی**\n\n"
        f"🆔 کد: `{record.tracking_code}`\n"
        f"👤 مالک: `{record.owner_id}`\n"
        f"🏷 برند: {record.brand}\n"
        f"🤖 Bot ID: `{record.bot_id}`\n"
        f"🌐 پنل: `{record.panel_url}`\n\n"
        "برای بررسی کامل، از پنل مدیریت مرکزی استفاده کنید."
    )

from __future__ import annotations

import asyncio

from telethon import Button, events

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.db.models import RegistrationStep, RegistrationStatus, RepresentativeRegistration
from app.services.pasarguard import PasarguardClient
from app.services.registration import RegistrationService
from app.services.registration_store import RegistrationStore
from app.services.secrets import get_secret_box
from app.services.telegram_bot import TelegramBotVerifier


STORE = RegistrationStore()
BOT_VERIFIER = TelegramBotVerifier()
_LOCKS: dict[int, asyncio.Lock] = {}

CANCEL = b"central:registration:cancel"
CONTINUE = b"central:registration:continue"
CONFIRM = b"central:registration:confirm"
BACK = b"central:registration:back"
ADMIN_PREFIX = b"central:admin:"

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


def _owner_lock(owner_id: int) -> asyncio.Lock:
    lock = _LOCKS.get(owner_id)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[owner_id] = lock
    return lock


async def _safe_answer(event, text: str | None = None) -> None:
    try:
        await event.answer(text or "")
    except Exception:
        pass


async def _safe_edit(event, text: str, buttons=None) -> bool:
    try:
        await event.edit(text, buttons=buttons)
        return True
    except Exception:
        try:
            await event.respond(text, buttons=buttons)
            return True
        except Exception:
            return False


async def continue_registration(event):
    if not _private(event):
        return
    await _safe_answer(event)
    try:
        async with _owner_lock(event.sender_id):
            record = await STORE.latest_for_owner(event.sender_id)
            if record is None:
                await _safe_edit(event, "❌ درخواست ثبت پیدا نشد. از منوی اصلی دوباره شروع کنید.")
                return
            if record.status != RegistrationStatus.DRAFT.value:
                await _safe_edit(event, "ℹ️ این درخواست دیگر در مرحله ورود اطلاعات نیست.")
                return
            step = RegistrationStep(record.step)
            if step == RegistrationStep.REVIEW:
                await _safe_edit(event, review_text(record), buttons=review_buttons())
                return
            prompt = PROMPTS.get(step)
            if not prompt:
                await _safe_edit(event, "❌ مرحله ثبت نام نامعتبر است. از منوی اصلی دوباره شروع کنید.")
                return
            await _safe_edit(event, prompt, buttons=wizard_buttons())
    except Exception as exc:
        print(f"[registration] continue error owner={event.sender_id}: {type(exc).__name__}: {exc}", flush=True)
        await _safe_edit(event, "❌ ادامه ثبت نام انجام نشد. لطفاً دوباره روی «ادامه ثبت» بزنید.", buttons=wizard_buttons())


async def input_router(event):
    if not _private(event) or not event.raw_text:
        return
    if event.raw_text.strip().lower() in {"/cancel", "cancel", "لغو"}:
        return
    owner_id = event.sender_id
    async with _owner_lock(owner_id):
        record = await STORE.latest_for_owner(owner_id)
        if record is None or record.status != RegistrationStatus.DRAFT.value:
            return
        step = RegistrationStep(record.step)
        if step == RegistrationStep.REVIEW:
            return
        value = event.raw_text.strip()
        progress = None
        try:
            progress = await event.respond("⏳ در حال بررسی اطلاعات شما...\n\nلطفاً چند لحظه صبر کنید.")
        except Exception:
            pass
        try:
            next_step, message = await process_step(record, step, value)
        except ValidationError as exc:
            prompt = PROMPTS.get(step, "لطفاً اطلاعات همین مرحله را دوباره ارسال کنید.")
            text = f"❌ {exc}\n\n{prompt}"
            if progress is not None:
                try:
                    await progress.edit(text, buttons=wizard_buttons())
                    return
                except Exception:
                    pass
            await event.respond(text, buttons=wizard_buttons())
            return
        except PermissionError as exc:
            text = f"❌ {exc}\n\nAPI Key را بررسی کنید و دوباره ارسال کنید."
            if progress is not None:
                try:
                    await progress.edit(text, buttons=wizard_buttons())
                    return
                except Exception:
                    pass
            await event.respond(text, buttons=wizard_buttons())
            return
        except Exception as exc:
            print(f"[registration] step error owner={owner_id} step={step.value}: {type(exc).__name__}: {exc}", flush=True)
            text = "❌ پردازش اطلاعات انجام نشد.\nلطفاً دوباره همین مرحله را ارسال کنید."
            if progress is not None:
                try:
                    await progress.edit(text, buttons=wizard_buttons())
                    return
                except Exception:
                    pass
            await event.respond(text, buttons=wizard_buttons())
            return
        if next_step == RegistrationStep.REVIEW:
            record = await STORE.latest_for_owner(owner_id)
            text = review_text(record, message)
            if progress is not None:
                try:
                    await progress.edit(text, buttons=review_buttons())
                    return
                except Exception:
                    pass
            await event.respond(text, buttons=review_buttons())
            return
        text = message or PROMPTS[next_step]
        if progress is not None:
            try:
                await progress.edit(text, buttons=wizard_buttons())
                return
            except Exception:
                pass
        await event.respond(text, buttons=wizard_buttons())


async def process_step(record: RepresentativeRegistration, step: RegistrationStep, value: str) -> tuple[RegistrationStep, str | None]:
    if step == RegistrationStep.BRAND:
        brand = RegistrationService.validate_brand(value)
        await STORE.update(record.id, brand=brand, step=RegistrationStep.BOT_TOKEN.value)
        return RegistrationStep.BOT_TOKEN, None
    if step == RegistrationStep.BOT_TOKEN:
        bot = await BOT_VERIFIER.get_me(value)
        await STORE.update(record.id, bot_id=int(bot["id"]), bot_token_encrypted=get_secret_box().encrypt(value), step=RegistrationStep.BOT_ID.value)
        return RegistrationStep.BOT_ID, f"✅ ربات `@{bot.get('username') or 'بدون نام کاربری'}` شناسایی شد.\n\n{PROMPTS[RegistrationStep.BOT_ID]}"
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
        probe = await client.probe()
        await STORE.update(record.id, panel_api_key_encrypted=get_secret_box().encrypt(value), step=RegistrationStep.REVIEW.value)
        test = probe.test_user
        sub = test.subscription_url or "در پاسخ API موجود نبود"
        return RegistrationStep.REVIEW, (
            "✅ **اتصال به پنل پاسارگارد موفق بود.**\n\n"
            f"👥 تعداد کلاینت‌ها بعد از ساخت تست: **{probe.client_count}**\n"
            f"🧪 کلاینت تستی: `{test.service_id}`\n"
            f"🔗 Subscription: `{sub}`\n\n"
            "کلاینت تستی برای تأیید واقعی اتصال ساخته شد."
        )
    raise ValidationError("مرحله ثبت نام نامعتبر است. از منوی اصلی دوباره شروع کنید.")


async def confirm_registration(event):
    if not _private(event):
        return
    await _safe_answer(event)
    async with _owner_lock(event.sender_id):
        record = await STORE.latest_for_owner(event.sender_id)
        if record is None or record.status != RegistrationStatus.DRAFT.value:
            await _safe_edit(event, "❌ درخواست قابل تأیید نیست.")
            return
        required = (record.brand, record.bot_id, record.bot_token_encrypted, record.panel_url, record.panel_username, record.panel_api_key_encrypted)
        if not all(required):
            await _safe_edit(event, "❌ اطلاعات ناقص است. به مراحل ثبت برگردید.", buttons=wizard_buttons())
            return
        await STORE.mark_pending(record.id)
    for admin_id in settings.admin_ids:
        try:
            await event.client.send_message(admin_id, admin_notification(record), buttons=admin_notification_buttons(record.id))
        except Exception:
            continue
    await _safe_edit(event, "✅ **درخواست ثبت شد**\n\n" f"🆔 کد پیگیری: `{record.tracking_code}`\n\nدرخواست برای بررسی ارسال شد.", buttons=[[Button.inline("🔎 مشاهده وضعیت", b"central:track:latest")]])


async def cancel_registration(event):
    if not _private(event):
        return
    await _safe_answer(event)
    await _safe_edit(event, "❌ فرایند ثبت متوقف شد. برای ادامه، از منوی اصلی دوباره ثبت نمایندگی را انتخاب کنید.")


async def back_registration(event):
    if not _private(event):
        return
    await _safe_answer(event)
    async with _owner_lock(event.sender_id):
        record = await STORE.latest_for_owner(event.sender_id)
        if record is None or record.status != RegistrationStatus.DRAFT.value:
            return
        previous = {RegistrationStep.BOT_TOKEN: RegistrationStep.BRAND, RegistrationStep.BOT_ID: RegistrationStep.BOT_TOKEN, RegistrationStep.PANEL_URL: RegistrationStep.BOT_ID, RegistrationStep.PANEL_USERNAME: RegistrationStep.PANEL_URL, RegistrationStep.PANEL_API_KEY: RegistrationStep.PANEL_USERNAME, RegistrationStep.REVIEW: RegistrationStep.PANEL_API_KEY}.get(RegistrationStep(record.step))
        if previous is None:
            await _safe_edit(event, PROMPTS[RegistrationStep.BRAND], buttons=wizard_buttons())
            return
        await STORE.set_step(record.id, previous)
        await _safe_edit(event, PROMPTS[previous], buttons=wizard_buttons())


def wizard_buttons():
    return [[Button.inline("🔙 مرحله قبل", BACK), Button.inline("❌ لغو", CANCEL)]]


def review_buttons():
    return [[Button.inline("✅ تأیید و ارسال", CONFIRM)], [Button.inline("🔙 اصلاح اطلاعات", BACK), Button.inline("❌ لغو", CANCEL)]]


def admin_notification_buttons(registration_id: int):
    return [
        [Button.inline("🔎 بررسی درخواست", ADMIN_PREFIX + f"view:{registration_id}".encode())],
        [Button.inline("✅ تأیید و شروع راه‌اندازی", ADMIN_PREFIX + f"approve:{registration_id}".encode()), Button.inline("❌ رد درخواست", ADMIN_PREFIX + f"reject_prompt:{registration_id}".encode())],
    ]


def review_text(record, probe_message: str | None = None) -> str:
    return ("📋 **بازبینی نهایی درخواست**\n\n" f"🏷 برند: {record.brand}\n" f"🤖 Bot ID: `{record.bot_id}`\n" f"🌐 پنل: `{record.panel_url}`\n" f"👤 نام کاربری پنل: `{record.panel_username}`\n" "🔐 API Key: `••••••••`\n\n" + (probe_message + "\n\n" if probe_message else "") + "اگر اطلاعات درست است، ارسال نهایی را بزنید.")


def admin_notification(record) -> str:
    return ("🔔 **درخواست جدید نمایندگی**\n\n" f"🆔 کد: `{record.tracking_code}`\n" f"👤 مالک: `{record.owner_id}`\n" f"🏷 برند: {record.brand}\n" f"🤖 Bot ID: `{record.bot_id}`\n" f"🌐 پنل: `{record.panel_url}`\n\n" "برای بررسی کامل، از پنل مدیریت مرکزی استفاده کنید.")

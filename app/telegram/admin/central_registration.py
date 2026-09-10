from __future__ import annotations

import re
import secrets

import httpx
from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.utils.text.markdown import escape
from app.logger import get_logger
from app.services.central_registry import (
    create_draft,
    get_active_for_owner,
    get_by_id,
    protect,
    update_registration,
)
from app.services.panels.auth import verify_panel_api_key, panel_api_error_text
from config import ADMIN_ID

logger = get_logger(__name__)

BRAND = "PRIMEVPN"


def _tracking_code() -> str:
    return f"PRIME-{secrets.token_hex(4).upper()}"


def _clean_panel_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if value.endswith("/dashboard"):
        value = value[: -len("/dashboard")]
    if "/dashboard/" in value:
        value = value.split("/dashboard/", 1)[0]
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    return value.rstrip("/")


def _main_menu():
    return [[Button.inline("🤖 ثبت ربات نمایندگی", b"prime:register")], [Button.inline("🔎 پیگیری درخواست", b"prime:track")]]


def _admin_buttons(registration_id: int):
    data = str(registration_id).encode()
    return [[Button.inline("✅ تأیید و فعال‌سازی", b"prime:approve:" + data), Button.inline("❌ رد درخواست", b"prime:reject:" + data)]]


async def _get_me(token: str) -> dict:
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        response.raise_for_status()
        payload = response.json()
    if not payload.get("ok") or not payload.get("result", {}).get("is_bot"):
        raise ValueError("توکن تلگرام معتبر نیست.")
    return payload["result"]


async def _notify_admins(text: str, buttons=None) -> None:
    for admin_id in ADMIN_ID:
        try:
            await Kenzo.send_message(admin_id, text, buttons=buttons)
        except Exception as exc:
            logger.warning("Could not notify central admin %s: %s", admin_id, exc)


@Kenzo.on(events.NewMessage(pattern=r"^/start$"))
async def central_start(event: Message) -> None:
    await event.respond(
        f"🌐 **{BRAND}**\n\nبه سامانه مرکزی نمایندگان خوش آمدید.\nاز اینجا می‌توانید ربات فروش خودتان را ثبت و پس از تأیید فعال کنید.",
        buttons=_main_menu(),
    )


@Kenzo.on(events.CallbackQuery(data=b"prime:register"))
async def start_registration(event) -> None:
    user_id = int(event.sender_id)
    existing = await get_active_for_owner(user_id)
    if existing:
        await event.answer("برای شما یک درخواست فعال وجود دارد.", alert=True)
        await event.edit(
            f"📋 درخواست فعال شما\n\nکد پیگیری: `{existing['tracking_code']}`\nوضعیت: `{existing['status']}`\nمرحله: `{existing['step']}`"
        )
        return
    registration_id = await create_draft(user_id, _tracking_code())
    await event.answer()
    await event.edit(
        "1️⃣ **ثبت ربات**\n\nابتدا **نام برند** خود را ارسال کنید.\nمثال: `MyVPN`"
    )
    logger.info("New representative registration id=%s owner=%s", registration_id, user_id)


@Kenzo.on(events.CallbackQuery(data=b"prime:track"))
async def track_registration(event) -> None:
    registration = await get_active_for_owner(int(event.sender_id))
    await event.answer()
    if not registration:
        await event.edit("هیچ درخواست فعالی برای شما پیدا نشد.", buttons=_main_menu())
        return
    await event.edit(
        f"🔎 **پیگیری درخواست**\n\nکد پیگیری: `{registration['tracking_code']}`\nوضعیت: `{registration['status']}`\nمرحله: `{registration['step']}`"
    )


@Kenzo.on(events.NewMessage(func=lambda e: e.is_private))
async def registration_messages(event: Message) -> None:
    if not event.raw_text or event.raw_text.startswith("/"):
        return

    user_id = int(event.sender_id)
    registration = await get_active_for_owner(user_id)
    if not registration or registration["status"] not in {"draft", "rejected"}:
        return

    rid = int(registration["id"])
    step = registration["step"]
    value = event.raw_text.strip()

    # Re-read by ID immediately before mutating so the message is bound to the
    # exact registration selected for this user, rather than relying on a stale
    # snapshot if another update for the same user completed concurrently.
    current = await get_by_id(rid)
    if not current or int(current["owner_user_id"]) != user_id:
        return
    if current["status"] not in {"draft", "rejected"} or current["step"] != step:
        return

    if step == "brand":
        if not 2 <= len(value) <= 120:
            await event.respond("❌ نام برند باید بین ۲ تا ۱۲۰ کاراکتر باشد. دوباره ارسال کنید.")
            return
        await update_registration(rid, brand=value, step="bot_token")
        await event.respond(
            "2️⃣ **اطلاعات ربات**\n\nتوکن رباتی که از BotFather گرفته‌اید را ارسال کنید.\nسپس شناسه عددی ربات هم از شما دریافت می‌شود."
        )
        return

    if step == "bot_token":
        try:
            me = await _get_me(value)
        except Exception as exc:
            await event.respond(f"❌ توکن نامعتبر است. دلیل: `{exc}`\nدوباره توکن صحیح را ارسال کنید.")
            return

        # The database row is the source of truth. Only this user's registration
        # ID is updated, so concurrent users cannot overwrite each other's token.
        current = await get_by_id(rid)
        if not current or int(current["owner_user_id"]) != user_id:
            return
        if current["status"] not in {"draft", "rejected"} or current["step"] != "bot_token":
            return

        await update_registration(
            rid,
            bot_token=protect(value),
            bot_id=int(me["id"]),
            bot_username=me.get("username"),
            step="bot_id",
        )
        await event.respond(
            f"✅ توکن صحیح است و ربات **@{me.get('username') or 'بدون‌نام'}** شناسایی شد.\n\nحالا **شناسه عددی ربات** را ارسال کنید."
        )
        return

    if step == "bot_id":
        if not value.isdigit():
            await event.respond("❌ شناسه ربات باید فقط عدد باشد. دوباره ارسال کنید.")
            return
        if int(value) != int(registration["bot_id"]):
            await event.respond("❌ شناسه عددی با توکن ربات مطابقت ندارد. شناسه صحیح را دوباره ارسال کنید.")
            return
        await update_registration(rid, step="panel_url")
        await event.respond("3️⃣ **اتصال پنل پاسارگاد**\n\nلینک ورود پنل پاسارگاد را ارسال کنید.")
        return

    if step == "panel_url":
        url = _clean_panel_url(value)
        if not re.match(r"^https?://[^\s]+$", url, re.I):
            await event.respond("❌ لینک پنل معتبر نیست. لینک کامل را دوباره ارسال کنید.")
            return
        await update_registration(rid, panel_url=url, step="panel_username")
        await event.respond("نام کاربری پنل پاسارگاد را ارسال کنید.")
        return

    if step == "panel_username":
        if not value:
            await event.respond("❌ نام کاربری خالی است. دوباره ارسال کنید.")
            return
        await update_registration(rid, panel_username=value, step="panel_api_key")
        await event.respond("حالا **API Key پنل پاسارگاد** را ارسال کنید.")
        return

    if step == "panel_api_key":
        try:
            current = await get_by_id(rid)
            await verify_panel_api_key(current["panel_url"], value)
        except Exception as exc:
            logger.info("Panel verification failed registration=%s: %s", rid, exc)
            await event.respond(
                f"❌ اتصال پنل تأیید نشد.\n\n`{panel_api_error_text(exc)}`\n\nاطلاعات صحیح را دوباره ارسال کنید."
            )
            return

        await update_registration(
            rid,
            panel_api_key=protect(value),
            status="pending",
            step="awaiting_admin",
            rejection_reason=None,
        )
        current = await get_by_id(rid)
        await event.respond(
            f"✅ پنل پاسارگاد با موفقیت تأیید شد.\n\n🎫 کد پیگیری: `{current['tracking_code']}`\n\nدرخواست شما برای مدیریت مرکزی ارسال شد. پس از تأیید، ربات نمایندگی با برند شما فعال می‌شود."
        )
        admin_text = (
            "🆕 **درخواست نمایندگی جدید**\n\n"
            f"🎫 کد: `{current['tracking_code']}`\n"
            f"👤 کاربر: `{current['owner_user_id']}`\n"
            f"🏷 برند: **{current['brand']}**\n"
            f"🤖 ربات: @{current['bot_username'] or 'unknown'}\n"
            f"🆔 Bot ID: `{current['bot_id']}`\n"
            f"🌐 پنل: `{current['panel_url']}`\n"
            f"👤 نام کاربری پنل: `{current['panel_username']}`\n\n"
            "API Key به‌صورت رمزنگاری‌شده ذخیره شده است."
        )
        await _notify_admins(admin_text, buttons=_admin_buttons(rid))
        return


@Kenzo.on(events.CallbackQuery(data=re.compile(rb"^prime:approve:\d+$")))
async def approve_registration(event) -> None:
    if int(event.sender_id) not in ADMIN_ID:
        await event.answer("دسترسی ندارید.", alert=True)
        return
    rid = int(event.data.rsplit(b":", 1)[1])
    registration = await get_by_id(rid)
    if not registration or registration["status"] != "pending":
        await event.answer("این درخواست دیگر در وضعیت قابل تأیید نیست.", alert=True)
        return
    await update_registration(rid, status="approved", step="provisioning")
    await event.answer("درخواست تأیید شد؛ فعال‌سازی در حال انجام است.")
    await event.edit("⏳ تأیید شد؛ فعال‌سازی ربات در حال انجام است...", parse_mode=None)
    from app.services.representative_provisioner import provision_representative

    try:
        result = await provision_representative(rid)
        await update_registration(rid, status="approved", step="active", **result)
        await Kenzo.send_message(
            registration["owner_user_id"],
            f"🎉 **نمایندگی شما فعال شد!**\n\n🏷 برند: **{registration['brand']}**\n🎫 کد پیگیری: `{registration['tracking_code']}`\n\n🤖 ربات نمایندگی شما آماده استفاده است."
        )
        await event.edit("✅ فعال‌سازی کامل شد.", parse_mode=None)
    except Exception as exc:
        logger.exception("Representative provisioning failed: %s", exc)
        await update_registration(rid, status="pending", step="awaiting_admin", rejection_reason=str(exc))
        await event.edit(f"⚠️ فعال‌سازی ناموفق: {exc}", parse_mode=None)


@Kenzo.on(events.CallbackQuery(data=re.compile(rb"^prime:reject:\d+$")))
async def reject_registration(event) -> None:
    if int(event.sender_id) not in ADMIN_ID:
        await event.answer("دسترسی ندارید.", alert=True)
        return
    rid = int(event.data.rsplit(b":", 1)[1])
    registration = await get_by_id(rid)
    if not registration or registration["status"] != "pending":
        await event.answer("این درخواست دیگر در وضعیت قابل رد نیست.", alert=True)
        return
    await update_registration(rid, status="rejected", step="brand", rejection_reason="توسط مدیریت مرکزی رد شد")
    await event.answer("رد شد")
    await event.edit("❌ درخواست رد شد.", parse_mode=None)
    await Kenzo.send_message(
        registration["owner_user_id"],
        f"❌ درخواست نمایندگی شما رد شد.\n\nکد پیگیری: `{registration['tracking_code']}`\nدوباره از منوی ثبت ربات اقدام کنید."
    )

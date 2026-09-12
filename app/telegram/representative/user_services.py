from __future__ import annotations

from datetime import datetime, timezone

from telethon import Button, events

from app.core.ids import USER_HOME
from app.db.models import ServiceSubscription, TenantRecord
from app.db.session import SessionFactory
from app.runtime.context import get_tenant, require_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.pasarguard import PasarguardClient, PasarguardUserDetails
from app.services.representative_users import SERVICE as USERS
from app.services.orders import SERVICE as ORDERS
from app.services.secrets import get_secret_box
from app.services.user_services import SERVICE
from app.services.logs import SERVICE as LOG_SERVICE

PREFIX = b"user:services:"


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await allowed(event):
                return await event.answer("دسترسی به این بخش را ندارید.", alert=True)
            try:
                await event.answer()
                await render_callback(event)
            except Exception as exc:
                await LOG_SERVICE.add("user.services.error", f"user={event.sender_id} error={type(exc).__name__}: {exc}", event.sender_id)
                try:
                    await event.answer("⚠️ خطایی هنگام بارگذاری سرویس‌ها رخ داد. لطفاً دوباره بزنید.", alert=True)
                except Exception:
                    pass

    client.add_event_handler(callback, events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))))


async def allowed(event):
    if not event.is_private or not get_tenant():
        return False
    user = await USERS.get_by_telegram_id(event.sender_id)
    return bool(user and not user.blocked)


def _status(service) -> str:
    if service.status == "active" and service.expires_at:
        expiry = service.expires_at.replace(tzinfo=timezone.utc) if service.expires_at.tzinfo is None else service.expires_at
        if expiry <= datetime.now(timezone.utc):
            return "⚫ منقضی‌شده"
    return {
        "pending_provisioning": "⏳ در انتظار تحویل",
        "provisioning": "🔄 در حال ساخت",
        "active": "🟢 فعال",
        "expired": "⚫ منقضی‌شده",
        "revoked": "🔴 لغوشده",
    }.get(service.status, str(service.status))


def _provider_status(details: PasarguardUserDetails, fallback: str) -> str:
    value = (details.status or "").lower().strip()
    labels = {
        "active": "🟢 فعال",
        "disabled": "🔴 غیرفعال",
        "expired": "⚫ منقضی‌شده",
        "limited": "🟠 محدودیت حجم",
        "limited_data": "🟠 محدودیت حجم",
        "on_hold": "🟡 در انتظار اولین استفاده",
    }
    if details.expire and details.expire <= datetime.now(timezone.utc):
        return "⚫ منقضی‌شده"
    return labels.get(value, fallback)


def _date(value):
    if not value:
        return "—"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if value.tzinfo else value.strftime("%Y-%m-%d %H:%M")


def _bytes(value: int | None) -> str:
    if value is None:
        return "نامحدود"
    size = float(max(0, value))
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.2f} {units[index]}"


def _remaining(details: PasarguardUserDetails) -> str:
    if details.data_limit is None or details.data_limit <= 0:
        return "نامحدود"
    return _bytes(max(0, details.data_limit - (details.used_traffic or 0)))


def _days_left(expire: datetime | None) -> str:
    if not expire:
        return "نامحدود"
    seconds = (expire - datetime.now(timezone.utc)).total_seconds()
    if seconds <= 0:
        return "۰ روز"
    days = int(seconds // 86400)
    return f"{days + 1} روز"


def _config_urls(subscription_url: str | None) -> list[tuple[str, str]]:
    if not subscription_url:
        return []
    base = subscription_url.rstrip("/")
    return [
        ("🔗 سابسکریپشن اصلی", base),
        ("🦋 Xray", f"{base}/xray"),
        ("🛡 Clash Meta", f"{base}/clash_meta"),
        ("🌐 Clash", f"{base}/clash"),
        ("📱 Sing-box", f"{base}/sing_box"),
        ("🟢 WireGuard", f"{base}/wireguard"),
        ("📐 Outline", f"{base}/outline"),
        ("📋 لینک‌ها", f"{base}/links"),
        ("📦 لینک‌های Base64", f"{base}/links_base64"),
    ]


async def _live_details(subscription_id: int, telegram_user_id: int):
    service = await SERVICE.subscription(telegram_user_id, subscription_id)
    if service is None:
        raise LookupError("سرویس پیدا نشد.")
    if not service.provider_service_id:
        return service, None

    tenant_id = require_tenant()
    async with SessionFactory() as session:
        tenant = await session.get(TenantRecord, tenant_id)
        if tenant is None:
            raise LookupError("نمایندگی پیدا نشد.")
        box = get_secret_box()
        api_key = box.decrypt(tenant.panel_api_key_encrypted)
        panel_url = tenant.panel_url

    details = await PasarguardClient(panel_url, api_key).get_user_by_id(service.provider_service_id)

    # Persist only provider facts that are safe to mirror locally. The user view
    # still works from the local record when the panel is temporarily offline.
    async with SessionFactory() as session:
        current = await session.get(ServiceSubscription, service.id)
        if current is not None:
            if details.subscription_url:
                current.subscription_url = details.subscription_url
            if details.service_id:
                current.provider_service_id = details.service_id
            if details.expire:
                current.expires_at = details.expire
            if details.status == "expired" or (details.expire and details.expire <= datetime.now(timezone.utc)):
                current.status = "expired"
            elif details.status == "active" and current.status not in {"revoked", "expired"}:
                current.status = "active"
            await session.commit()
            await session.refresh(current)
            service = current
    return service, details


async def _user_pending_orders(telegram_user_id: int):
    # OrderService intentionally exposes tenant-scoped list/get methods only.
    # Never call a non-existent list_for_user helper from the Telegram layer.
    orders = await ORDERS.list(status="pending", limit=50)
    return [order for order in orders if order.telegram_user_id == telegram_user_id][:10]


async def render_user(telegram_user_id: int):
    services = await SERVICE.subscriptions(telegram_user_id, limit=50)
    pending_orders = await _user_pending_orders(telegram_user_id)
    if not services and not pending_orders:
        return (
            "📦 سرویس‌های من\n\nهنوز سرویسی برای شما ساخته نشده است.",
            [[Button.inline("🛍 خرید سرویس", b"user:buy")], [Button.inline("🔙 فروشگاه", b"user:" + USER_HOME.encode())]],
        )
    active = [s for s in services if _status(s) == "🟢 فعال"]
    pending = [s for s in services if s.status in {"pending_provisioning", "provisioning"}]
    expired = [s for s in services if _status(s) == "⚫ منقضی‌شده"]
    text = (
        "📦 سرویس‌های من\n\n"
        f"🟢 فعال: {len(active)}\n"
        f"⏳ در حال تحویل: {len(pending)}\n"
        f"⚫ منقضی: {len(expired)}\n"
        f"🧾 پرداخت‌های نیمه‌تمام: {len(pending_orders)}\n"
        f"📋 مجموع سرویس‌ها: {len(services)}"
    )
    buttons = [[Button.inline(f"💳 ادامه پرداخت #{o.id} · {o.plan_name}", b"user:order:resume:" + str(o.id).encode())] for o in pending_orders]
    if services:
        text += "\n\nسرویس موردنظر را انتخاب کنید:"
        buttons += [[Button.inline(f"#{s.id} • {s.plan_name} • {_status(s)}", PREFIX + f"view:{s.id}".encode())] for s in services[:20]]
    buttons += [[Button.inline("🔄 بروزرسانی", PREFIX + b"list")], [Button.inline("🛍 خرید سرویس", b"user:buy")], [Button.inline("🔙 فروشگاه", b"user:" + USER_HOME.encode())]]
    return text, buttons


async def _detail_text(service, details: PasarguardUserDetails | None, error: str | None = None) -> str:
    status = _provider_status(details, _status(service)) if details else _status(service)
    used = _bytes(details.used_traffic) if details else "—"
    limit = _bytes(details.data_limit) if details else f"{service.volume_gb:g} GB"
    remaining = _remaining(details) if details else "—"
    expire = details.expire if details and details.expire else service.expires_at
    days_left = _days_left(expire)
    provider_id = details.service_id if details else service.provider_service_id or "—"
    username = details.username if details and details.username else f"tg_{service.telegram_user_id}_{service.order_id}"
    text = (
        f"📦 سرویس #{service.id}\n\n"
        f"📌 پلن: {service.plan_name}\n"
        f"👤 شناسه: {username}\n"
        f"🆔 شناسه پاسارگارد: {provider_id}\n"
        f"📊 وضعیت: {status}\n"
        f"💾 حجم مصرف‌شده: {used}\n"
        f"📦 سقف حجم: {limit}\n"
        f"🟩 حجم باقی‌مانده: {remaining}\n"
        f"🟢 شروع: {_date(service.starts_at)}\n"
        f"⏰ انقضا: {_date(expire)}\n"
        f"⏳ زمان باقی‌مانده: {days_left}"
    )
    if error:
        text += f"\n\n⚠️ بروزرسانی لحظه‌ای انجام نشد: {error[:180]}"
    return text


async def _send_credentials(event, service, details: PasarguardUserDetails | None = None):
    subscription_url = (details.subscription_url if details else None) or service.subscription_url
    urls = _config_urls(subscription_url)
    if not urls:
        return await event.respond("⚠️ لینک اشتراک هنوز برای این سرویس آماده نشده است.")
    await event.respond(f"🔗 سابسکریپشن سرویس #{service.id}\n\n{urls[0][1]}")
    config_text = "📥 کانفیگ‌های سرویس\n\n" + "\n".join(f"{label}:\n{url}" for label, url in urls[1:])
    await event.respond(config_text)


async def render_callback(event):
    action = event.data[len(PREFIX):].decode(errors="ignore")
    if action in ("", "list"):
        text, buttons = await render_user(event.sender_id)
        return await event.edit(text, buttons=buttons)

    if action.startswith("view:"):
        try:
            sid = int(action.split(":", 1)[1])
        except ValueError:
            return await event.answer("شناسه سرویس نامعتبر است.", alert=True)
        service = await SERVICE.subscription(event.sender_id, sid)
        if service is None:
            return await event.answer("سرویس پیدا نشد.", alert=True)
        details = None
        live_error = None
        try:
            service, details = await _live_details(sid, event.sender_id)
        except Exception as exc:
            live_error = str(exc)
        status = _provider_status(details, _status(service)) if details else _status(service)
        buttons = []
        subscription_url = (details.subscription_url if details else None) or service.subscription_url
        config_urls = _config_urls(subscription_url)
        if config_urls:
            buttons.append([Button.url("🔗 لینک اشتراک", config_urls[0][1])])
            buttons.append([Button.url("🦋 Xray", config_urls[1][1]), Button.url("🛡 Clash Meta", config_urls[2][1])])
            buttons.append([Button.url("🌐 Clash", config_urls[3][1]), Button.url("📱 Sing-box", config_urls[4][1])])
            buttons.append([Button.url("🟢 WireGuard", config_urls[5][1]), Button.url("📐 Outline", config_urls[6][1])])
            buttons.append([Button.inline("📨 ارسال ساب + کانفیگ‌ها", PREFIX + f"send:{sid}".encode())])
        if service.plan_id and status not in {"⏳ در انتظار تحویل", "🔄 در حال ساخت"}:
            buttons.append([Button.inline("🔄 تمدید / خرید مجدد همین پلن", b"user:order:" + str(service.plan_id).encode())])
        buttons += [[Button.inline("🔄 بروزرسانی لحظه‌ای", PREFIX + f"view:{sid}".encode())], [Button.inline("🔙 سرویس‌های من", PREFIX + b"list")]]
        return await event.edit(await _detail_text(service, details, live_error), buttons=buttons)

    if action.startswith("send:"):
        try:
            sid = int(action.split(":", 1)[1])
        except ValueError:
            return await event.answer("شناسه سرویس نامعتبر است.", alert=True)
        service = await SERVICE.subscription(event.sender_id, sid)
        if service is None:
            return await event.answer("سرویس پیدا نشد.", alert=True)
        details = None
        try:
            service, details = await _live_details(sid, event.sender_id)
        except Exception:
            pass
        await event.answer("📨 در حال ارسال لینک‌ها...")
        await _send_credentials(event, service, details)
        return

    await event.answer("گزینه نامعتبر است.", alert=True)

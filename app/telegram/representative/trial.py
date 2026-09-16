from __future__ import annotations

from telethon import Button, events

from app.core.ids import USER_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_users import SERVICE as USERS
from app.services.trial import SERVICE

PREFIX = b"user:trial"
HOME_CALLBACK = b"user:home"


def register(client, tenant_id=None):
    async def callback(event):
        async with tenant_dispatch(tenant_id):
            if not await allowed(event):
                return await event.answer("دسترسی به این بخش را ندارید.", alert=True)
            try:
                await render_callback(event)
            except Exception as exc:
                try:
                    await event.edit(
                        "⚠️ سرویس آزمایشی ساخته شد، اما نمایش نتیجه با خطا مواجه شد.\n\n"
                        "از «سرویس‌های من» می‌توانید سرویس و کانفیگ را دریافت کنید.",
                        buttons=[[Button.inline("📦 سرویس‌های من", b"user:services")], [Button.inline("🏪 فروشگاه", HOME_CALLBACK)]],
                        parse_mode=None,
                    )
                except Exception:
                    pass
                raise exc

    client.add_event_handler(
        callback,
        events.CallbackQuery(func=lambda e: bool(e.data and e.data.startswith(PREFIX))),
    )


async def allowed(event):
    if not event.is_private or not get_tenant():
        return False
    user = await USERS.get_by_telegram_id(event.sender_id)
    return bool(user and not user.blocked)


async def render_callback(event):
    action = event.data[len(PREFIX):].decode(errors="ignore").lstrip(":")
    if action in ("", "claim"):
        try:
            plan, subscription, config_name = await SERVICE.claim(event.sender_id)
        except (ValueError, LookupError) as exc:
            return await event.edit(
                f"🎁 **سرویس آزمایشی**\n\n❌ {exc}",
                buttons=[[Button.inline("🔙 فروشگاه", HOME_CALLBACK)]],
            )
        except Exception as exc:
            return await event.edit(
                "🎁 **سرویس آزمایشی**\n\n"
                "❌ ساخت سرویس در پاسارگارد انجام نشد.\n\n"
                f"{str(exc)[:300]}",
                buttons=[
                    [Button.inline("🔄 تلاش دوباره", PREFIX + b"claim")],
                    [Button.inline("🔙 فروشگاه", HOME_CALLBACK)],
                ],
            )

        settings = await SERVICE.snapshot()
        raw_value = settings.get("trial_volume_value", "1")
        try:
            trial_value = float(raw_value)
            volume_text = f"{trial_value:g}"
        except (TypeError, ValueError):
            volume_text = str(raw_value)
        trial_unit = str(settings.get("trial_volume_unit", "GB")).upper()
        trial_days = str(settings.get("trial_days", "1"))

        rows = [
            [Button.inline("📦 سرویس‌های من", b"user:services")],
            [Button.inline("🏪 فروشگاه", HOME_CALLBACK)],
        ]
        if subscription.subscription_url:
            rows.insert(0, [Button.url("🔗 لینک اشتراک", subscription.subscription_url)])

        return await event.edit(
            "🎉 **سرویس آزمایشی فعال شد**\n\n"
            f"📦 پلن: **{plan.name}**\n"
            f"🏷 نام کانفیگ: `{config_name}`\n"
            f"💾 حجم: **{volume_text} {trial_unit}**\n"
            f"📅 مدت: **{trial_days} روز**\n\n"
            "✅ سرویس در پاسارگارد ساخته و فعال شد.\n"
            "📦 برای دریافت کانفیگ، روی «سرویس‌های من» بزنید.\n"
            "🔗 از داخل سرویس می‌توانید لینک اشتراک و کانفیگ Xray را دریافت کنید.",
            buttons=rows,
        )

    await event.answer("گزینه نامعتبر است.", alert=True)

from __future__ import annotations

import asyncio
import hashlib
import logging

from telethon import TelegramClient, Button, events
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.representative_users import SERVICE as USER_SERVICE
from app.services.texts import SERVICE as TEXT_SERVICE
from app.services.referrals import SERVICE as REFERRAL_SERVICE
from app.services.representative_settings import SERVICE as SETTINGS
from app.telegram.representative.force_join import ForceJoinError, channel_url, is_user_member, validate_channel_admin

logger = logging.getLogger(__name__)


def _token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


class RepresentativeRuntime:
    def __init__(self, tenant_id: str, bot_token: str):
        self.tenant_id = tenant_id
        self.bot_token = bot_token.strip()
        self.client = TelegramClient(f"tenant-{tenant_id}")
        self.is_running = False
        self._polling_task: asyncio.Task | None = None
        self.dashboard = RepresentativeDashboardService()

    def register(self):
        self.client.add_event_handler(self._force_join_message, events.NewMessage(incoming=True))
        self.client.add_event_handler(self._force_join_callback, events.CallbackQuery())
        self.client.add_event_handler(self._start, events.NewMessage(pattern=r"^/start(?:\s+(.+))?$"))
        from app.telegram.representative.admin import register as a
        from app.telegram.representative.plans import register as p
        from app.telegram.representative.users import register as u
        from app.telegram.representative.orders import register as o
        from app.telegram.representative.services import register as sv
        from app.telegram.representative.discounts import register as d
        from app.telegram.representative.sales import register as s
        from app.telegram.representative.texts import register as t
        from app.telegram.representative.logs import register as l
        from app.telegram.representative.links import register as k
        from app.telegram.representative.settings import register as r
        from app.telegram.representative.panel import register as h
        from app.telegram.representative.navigation import register as n
        from app.telegram.representative.checkout import register as co
        from app.telegram.representative.user_services import register as us
        from app.telegram.representative.wallet import register as w
        from app.telegram.representative.profile import register as pr
        from app.telegram.representative.discount_user import register as du
        from app.telegram.representative.trial import register as tr
        from app.telegram.representative.referral import register as rf
        from app.telegram.representative.support import register as sp
        from app.telegram.representative.support_admin import register as spa
        a(self.client, self.tenant_id)
        p(self.client, self.tenant_id)
        u(self.client, self.tenant_id)
        o(self.client, self.tenant_id)
        sv(self.client, self.tenant_id)
        d(self.client, self.tenant_id)
        s(self.client, self.tenant_id)
        t(self.client, self.tenant_id)
        l(self.client, self.tenant_id)
        k(self.client, self.tenant_id)
        r(self.client, self.tenant_id, self.bot_token)
        h(self.client, self.tenant_id)
        co(self.client, self.tenant_id)
        n(self.client, self.tenant_id)
        us(self.client, self.tenant_id)
        w(self.client, self.tenant_id)
        pr(self.client, self.tenant_id)
        du(self.client, self.tenant_id)
        tr(self.client, self.tenant_id)
        rf(self.client, self.tenant_id)
        sp(self.client, self.tenant_id)
        spa(self.client, self.tenant_id)

    async def _force_join_required(self, event) -> bool:
        if not event.is_private or await self.dashboard.is_owner(event.sender_id):
            return False
        channel_id = (await SETTINGS.snapshot()).get("force_join_channel_id", "").strip()
        if not channel_id:
            return False
        try:
            return not await is_user_member(self.bot_token, int(channel_id), event.sender_id)
        except Exception:
            return True

    async def _force_join_message(self, event):
        async with tenant_dispatch(self.tenant_id):
            if not await self._force_join_required(event):
                return
            channel_id = (await SETTINGS.snapshot()).get("force_join_channel_id", "").strip()
            url = None
            try:
                chat = await validate_channel_admin(self.bot_token, int(channel_id))
                url = channel_url(chat)
            except Exception:
                pass
            buttons = [[Button.url("📢 عضویت در کانال", url)]] if url else []
            buttons.append([Button.inline("✅ بررسی عضویت", b"forcejoin:check")])
            await event.respond(
                "🔒 **عضویت اجباری**\n\nبرای استفاده از ربات ابتدا در کانال اعلام‌شده عضو شوید و سپس «بررسی عضویت» را بزنید.",
                buttons=buttons,
            )
            try:
                event.stop_propagation()
            except Exception:
                pass

    async def _force_join_callback(self, event):
        async with tenant_dispatch(self.tenant_id):
            data = bytes(event.data or b"")
            if data != b"forcejoin:check":
                if await self._force_join_required(event):
                    await event.answer("ابتدا باید عضو کانال شوید.", alert=True)
                    try:
                        event.stop_propagation()
                    except Exception:
                        pass
                return
            if await self._force_join_required(event):
                return await event.answer("هنوز عضویت شما تأیید نشده است.", alert=True)
            await event.answer("✅ عضویت تأیید شد.", alert=True)
            try:
                await event.respond("اکنون می‌توانید از ربات استفاده کنید.")
            except Exception:
                pass
            try:
                event.stop_propagation()
            except Exception:
                pass

    async def _start(self, event):
        async with tenant_dispatch(self.tenant_id):
            if await self._force_join_required(event):
                return

            # /start must not clear the chat or delete the start message.
            # Doing that made the Telegram bot screen appear to kick the user out
            # immediately after pressing Start. The bot now simply opens normally.
            user = await USER_SERVICE.upsert_from_sender(await event.get_sender())
            if user.blocked:
                return await event.respond(await TEXT_SERVICE.get("blocked_user"))

            ref_arg = event.pattern_match.group(1) if event.pattern_match else None
            if ref_arg and ref_arg.strip().startswith("ref_"):
                try:
                    await REFERRAL_SERVICE.attach(int(ref_arg.strip()[4:]), event.sender_id)
                except (ValueError, LookupError):
                    pass

            values = await TEXT_SERVICE.all()
            from app.telegram.representative.navigation import customer_menu
            is_owner = await self.dashboard.is_owner(event.sender_id)
            await event.respond(values["welcome"], buttons=await customer_menu(values, is_owner))

    async def start(self):
        if self.is_running:
            return
        self.register()
        try:
            await self.client.start(bot_token=self.bot_token)
            logger.info(
                "[representative-runtime] initialized tenant=%s bot_id=%s bot_username=%s token_fp=%s",
                self.tenant_id,
                getattr(getattr(self.client, "_me", None), "id", "unknown"),
                getattr(getattr(self.client, "_me", None), "username", "") or "",
                _token_fingerprint(self.bot_token),
            )
            self._polling_task = asyncio.create_task(
                self.client.run_until_disconnected(),
                name=f"representative-poll-{self.tenant_id}",
            )
            self._polling_task.add_done_callback(self._polling_done)
            self.is_running = True
        except Exception:
            await self.client.disconnect()
            self._polling_task = None
            self.is_running = False
            raise

    def _polling_done(self, task: asyncio.Task) -> None:
        if self._polling_task is not task:
            return
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "[representative-runtime] polling task exited tenant=%s token_fp=%s error=%s",
                self.tenant_id,
                _token_fingerprint(self.bot_token),
                exc,
                exc_info=exc,
            )
        else:
            logger.warning(
                "[representative-runtime] polling task exited unexpectedly tenant=%s",
                self.tenant_id,
            )
        self.is_running = False

    async def stop(self):
        task = self._polling_task
        self._polling_task = None
        self.is_running = False
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self.client.disconnect()

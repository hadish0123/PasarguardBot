from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient

from app.core.config import settings
from app.db.session import initialize_database
from app.services.tenant import TenantService
from app.telegram.central import register_central_handlers
from app.telegram.central.admin import register_central_admin_handlers
from app.telegram.representative.registry import registry

logger = logging.getLogger(__name__)


# Telegram rejects dynamic Markdown when user/provider data contains characters
# that are meaningful to the Markdown parser. Keep the normal Markdown path,
# but transparently retry the edit as plain text so callback handlers cannot die
# just because a detail field contains an underscore or another special char.
_original_edit_message = TelegramClient.edit_message


async def _safe_edit_message(self, entity, message_id: int, text: str, *, buttons=None, **kwargs):
    try:
        return await _original_edit_message(self, entity, message_id, text, buttons=buttons, **kwargs)
    except RuntimeError as exc:
        message = str(exc).lower()
        if "can't parse entities" not in message and "parse entities" not in message:
            raise
        retry_kwargs = dict(kwargs)
        retry_kwargs["parse_mode"] = None
        return await _original_edit_message(self, entity, message_id, text, buttons=buttons, **retry_kwargs)


TelegramClient.edit_message = _safe_edit_message


async def run(stop_event: asyncio.Event | None = None) -> None:
    print("[telegram-runtime] run() entered", flush=True)
    if not settings.central_bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    print("[telegram-runtime] initializing database", flush=True)
    await initialize_database()
    print("[telegram-runtime] database initialized", flush=True)

    client = TelegramClient("central")
    print("[telegram-runtime] TelegramClient created", flush=True)
    register_central_handlers(client)
    print("[telegram-runtime] central handlers registered", flush=True)
    register_central_admin_handlers(client)
    print("[telegram-runtime] central admin handlers registered", flush=True)
    print("[telegram-runtime] starting central bot", flush=True)
    await client.start(bot_token=settings.central_bot_token)
    print("[telegram-runtime] central bot started", flush=True)

    tenant_service = TenantService()
    tenants = await tenant_service.list_runtime_tenants(settings.central_bot_token)
    print(f"[telegram-runtime] runtime tenants: {len(tenants)}", flush=True)
    for tenant in tenants:
        try:
            await registry.start(tenant.id, tenant.bot_token)
            print(f"[telegram-runtime] representative runtime restored: {tenant.id}", flush=True)
        except Exception:
            logger.exception("failed to restore representative runtime: %s", tenant.id)
            print(f"[telegram-runtime] representative restore failed: {tenant.id}", flush=True)

    print("[telegram-runtime] entering update loop", flush=True)
    if stop_event is None:
        try:
            await client.run_until_disconnected()
        finally:
            await _stop_representative_runtimes()
        return

    try:
        await stop_event.wait()
    finally:
        await client.disconnect()
        await _stop_representative_runtimes()


async def _stop_representative_runtimes() -> None:
    tenants = await TenantService().list_runtime_tenants(settings.central_bot_token)
    for tenant in tenants:
        try:
            await registry.stop(tenant.id)
        except Exception:
            logger.exception("failed to stop representative runtime: %s", tenant.id)

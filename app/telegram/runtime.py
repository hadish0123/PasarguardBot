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


async def run(stop_event: asyncio.Event | None = None) -> None:
    if not settings.central_bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    await initialize_database()

    # The local telethon compatibility facade is Bot API-only. API_ID/API_HASH
    # are intentionally not required anywhere in the application runtime.
    client = TelegramClient("central")
    register_central_handlers(client)
    register_central_admin_handlers(client)
    await client.start(bot_token=settings.central_bot_token)

    # Never start a representative runtime with the central bot token. A tenant
    # accidentally registered with BOT_TOKEN would otherwise create a second
    # getUpdates consumer and Telegram would terminate one of the connections.
    tenant_service = TenantService()
    for tenant in await tenant_service.list_runtime_tenants(settings.central_bot_token):
        try:
            await registry.start(tenant.id, tenant.bot_token)
            logger.info("representative runtime restored: %s", tenant.id)
        except Exception:
            logger.exception("failed to restore representative runtime: %s", tenant.id)

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

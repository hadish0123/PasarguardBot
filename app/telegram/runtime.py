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
    if not settings.telegram_api_id or not settings.telegram_api_hash or not settings.central_bot_token:
        raise RuntimeError("API_ID, API_HASH and BOT_TOKEN are required")

    await initialize_database()

    client = TelegramClient("central", settings.telegram_api_id, settings.telegram_api_hash)
    register_central_handlers(client)
    register_central_admin_handlers(client)
    await client.start(bot_token=settings.central_bot_token)

    # Railway/container restarts must not silently leave active representative
    # tenants offline. Restore only tenants persisted as ACTIVE and keep every
    # bot isolated in its own RepresentativeRuntime.
    tenant_service = TenantService()
    for tenant in await tenant_service.list_runtime_tenants():
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
    tenants = await TenantService().list_runtime_tenants()
    for tenant in tenants:
        try:
            await registry.stop(tenant.id)
        except Exception:
            logger.exception("failed to stop representative runtime: %s", tenant.id)

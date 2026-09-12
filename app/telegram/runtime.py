from __future__ import annotations

import asyncio
import hashlib
import html
import logging

import uvicorn
from telethon import TelegramClient

from app.core.config import settings
from app.db.session import initialize_database
from app.services.tenant import TenantService
from app.telegram.central import register_central_handlers
from app.telegram.central.admin import register_central_admin_handlers
from app.telegram.central.order_tracking import install_order_tracking
from app.telegram.representative.registry import registry
from app.web_admin import create_web_admin_app

logger = logging.getLogger(__name__)


def _token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


_original_edit_message = TelegramClient.edit_message


async def _safe_edit_message(self, entity, message_id: int, text: str, *, buttons=None, **kwargs):
    try:
        return await _original_edit_message(self, entity, message_id, text, buttons=buttons, **kwargs)
    except RuntimeError as exc:
        message = str(exc).lower()
        if "message is not modified" in message:
            logger.debug("Telegram edit skipped: message is not modified")
            return None
        if "can't parse entities" not in message and "parse entities" not in message:
            raise
        retry_kwargs = dict(kwargs)
        retry_kwargs["parse_mode"] = "HTML"
        retry_text = html.escape(str(text), quote=False)
        logger.warning("Markdown edit failed; retrying safely as escaped HTML")
        return await _original_edit_message(
            self,
            entity,
            message_id,
            retry_text,
            buttons=buttons,
            **retry_kwargs,
        )


TelegramClient.edit_message = _safe_edit_message


async def _start_representative(tenant) -> bool:
    try:
        await registry.start(tenant.id, tenant.bot_token)
        logger.info("[telegram-runtime] representative runtime restored: %s", tenant.id)
        return True
    except Exception:
        logger.exception("failed to restore representative runtime: %s", tenant.id)
        return False


async def _restore_representative_runtimes(tenants) -> tuple[int, int]:
    """Restore bots concurrently with a bounded fan-out."""
    if not tenants:
        return 0, 0
    semaphore = asyncio.Semaphore(20)

    async def worker(tenant):
        async with semaphore:
            return await _start_representative(tenant)

    results = await asyncio.gather(*(worker(tenant) for tenant in tenants), return_exceptions=False)
    return sum(1 for ok in results if ok), sum(1 for ok in results if not ok)


async def _start_web_server() -> uvicorn.Server:
    """Start HTTP/Web Admin immediately; never depend on Telegram polling."""
    app = create_web_admin_app()
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.fastapi_port,
        log_level="warning",
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve(), name="web-admin-server")
    logger.info("[web-admin] HTTP server starting on 0.0.0.0:%s", settings.fastapi_port)
    return server


async def run(stop_event: asyncio.Event | None = None) -> None:
    print("[telegram-runtime] run() entered", flush=True)

    # The HTTP listener is deliberately started before Telegram. Railway's
    # healthcheck must remain independent from Telegram startup/polling.
    web_server = await _start_web_server()

    if not settings.central_bot_token:
        web_server.should_exit = True
        raise RuntimeError("BOT_TOKEN is required")

    print("[telegram-runtime] initializing database", flush=True)
    await initialize_database()
    print("[telegram-runtime] database initialized", flush=True)

    client = TelegramClient("central")
    print("[telegram-runtime] TelegramClient created", flush=True)
    register_central_handlers(client)
    print("[telegram-runtime] central handlers registered", flush=True)
    register_central_admin_handlers(client)
    install_order_tracking(client)
    print("[telegram-runtime] central admin handlers registered", flush=True)
    print("[telegram-runtime] starting central bot", flush=True)
    await client.start(bot_token=settings.central_bot_token)
    logger.info(
        "[central-runtime] initialized bot_id=%s bot_username=%s token_fp=%s",
        getattr(getattr(client, "_me", None), "id", "unknown"),
        getattr(getattr(client, "_me", None), "username", "") or "",
        _token_fingerprint(settings.central_bot_token),
    )
    print("[telegram-runtime] central bot started", flush=True)

    tenant_service = TenantService()
    tenants = await tenant_service.list_runtime_tenants(settings.central_bot_token)
    print(f"[telegram-runtime] runtime tenants: {len(tenants)}", flush=True)
    restored, failed = await _restore_representative_runtimes(tenants)
    print(
        f"[telegram-runtime] representative runtimes restored: {restored}; failed: {failed}",
        flush=True,
    )

    print("[telegram-runtime] entering update loop", flush=True)
    try:
        if stop_event is None:
            await client.run_until_disconnected()
        else:
            await stop_event.wait()
    finally:
        await client.disconnect()
        await _stop_representative_runtimes()
        web_server.should_exit = True
        logger.info("[web-admin] HTTP server shutdown requested")


async def _stop_representative_runtimes() -> None:
    tenants = await TenantService().list_runtime_tenants(settings.central_bot_token)
    semaphore = asyncio.Semaphore(20)

    async def worker(tenant):
        async with semaphore:
            try:
                await registry.stop(tenant.id)
            except Exception:
                logger.exception("failed to stop representative runtime: %s", tenant.id)

    await asyncio.gather(*(worker(tenant) for tenant in tenants))

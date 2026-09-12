from __future__ import annotations

import asyncio
import html
import logging

from telethon import TelegramClient

from app.core.config import settings
from app.db.session import initialize_database
from app.services.tenant import TenantService
from app.telegram.central import register_central_handlers
from app.telegram.central.admin import register_central_admin_handlers
from app.telegram.representative.registry import registry

logger = logging.getLogger(__name__)


# Telegram rejects dynamic Markdown when runtime data contains characters that
# have special meaning to the Markdown parser. Keep the normal Markdown path,
# but retry failed edits using HTML with the entire message escaped. This makes
# the fallback safe even when the text contains underscores, brackets, asterisks,
# backticks, or user/provider supplied angle brackets.
_original_edit_message = TelegramClient.edit_message


async def _safe_edit_message(self, entity, message_id: int, text: str, *, buttons=None, **kwargs):
    try:
        return await _original_edit_message(self, entity, message_id, text, buttons=buttons, **kwargs)
    except RuntimeError as exc:
        message = str(exc).lower()
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
    
    # Spawn polling tasks for central and all representative runtimes that own their tokens
    polling_tasks = []
    
    # Central bot polling
    central_polling = asyncio.create_task(
        client.run_until_disconnected(),
        name="central-polling"
    )
    polling_tasks.append(central_polling)
    
    # Representative polling (only for polling owners)
    for tenant in tenants:
        runtime = registry.get(tenant.id)
        if runtime and registry.is_polling_owner(tenant.id):
            task = asyncio.create_task(
                runtime._run_polling(),
                name=f"representative-polling-{tenant.id}"
            )
            polling_tasks.append(task)
    
    if stop_event is None:
        try:
            # Wait for all polling tasks; if any fails, propagate
            _, pending = await asyncio.wait(polling_tasks, return_when=asyncio.FIRST_EXCEPTION)
            for task in polling_tasks:
                if task.done() and task.exception():
                    raise task.exception()
        except asyncio.CancelledError:
            pass
        finally:
            await _stop_representative_runtimes()
        return

    try:
        # Wait for stop event while polling runs in background
        await stop_event.wait()
    finally:
        await client.disconnect()
        for task in polling_tasks:
            if not task.done():
                task.cancel()
        try:
            await asyncio.gather(*polling_tasks, return_exceptions=True)
        except Exception:
            pass
        await _stop_representative_runtimes()


async def _stop_representative_runtimes() -> None:
    tenants = await TenantService().list_runtime_tenants(settings.central_bot_token)
    for tenant in tenants:
        try:
            await registry.stop(tenant.id)
        except Exception:
            logger.exception("failed to stop representative runtime: %s", tenant.id)

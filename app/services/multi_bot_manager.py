from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.custom_telethon import TelegramClient
from app.logger import get_logger
from app.logger.telethon import register_telethon_client, unregister_telethon_client
from app.runtime.context import TenantRuntime, client_context, tenant_context
from app.services.central_registry import get_approved, get_by_id, reveal, update_registration
from app.services.representative_bootstrap import ensure_representative_panel
from app.services.representative_provisioner import provision_representative, tenant_database_url

logger = get_logger("multi_bot_manager")


@dataclass
class RepresentativeRuntime:
    registration_id: int
    tenant: TenantRuntime
    client: TelegramClient
    task: asyncio.Task | None = None


class MultiBotManager:
    """Own all representative Bot API runtimes inside the single Railway service."""

    def __init__(self, central_client: TelegramClient):
        self.central_client = central_client
        self._runtimes: dict[int, RepresentativeRuntime] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._stopping = False
        self._supervisor_task: asyncio.Task | None = None

    def _lock(self, registration_id: int) -> asyncio.Lock:
        return self._locks.setdefault(registration_id, asyncio.Lock())

    def _handler_copy(self):
        return [
            item
            for item in self.central_client._handlers
            if not getattr(item[0], "__module__", "").endswith("central_registration")
        ]

    async def _build_tenant(self, registration: dict) -> TenantRuntime:
        database = registration.get("tenant_db_name") or f"primevpn_rep_{int(registration['id'])}"
        return TenantRuntime(
            registration_id=int(registration["id"]),
            owner_user_id=int(registration["owner_user_id"]),
            bot_id=int(registration["bot_id"]),
            bot_username=registration.get("bot_username"),
            brand=str(registration.get("brand") or "Representative"),
            database_url=tenant_database_url(database),
            panel_url=str(registration["panel_url"]),
            panel_username=str(registration.get("panel_username") or "-"),
            panel_api_key=reveal(registration["panel_api_key"]),
        )

    async def start_for_registration(self, registration_id: int, *, provision: bool = True) -> RepresentativeRuntime:
        async with self._lock(registration_id):
            existing = self._runtimes.get(registration_id)
            if existing and existing.client.is_connected():
                return existing

            registration = await get_by_id(registration_id)
            if not registration:
                raise RuntimeError("Registration not found")
            status = str(registration["status"])
            if status not in {"approved", "provisioning", "active"}:
                raise RuntimeError(f"Registration {registration_id} is not approved")

            if provision or not registration.get("tenant_db_name"):
                result = await provision_representative(registration_id)
                await update_registration(registration_id, **result)
                registration = await get_by_id(registration_id)
                if not registration:
                    raise RuntimeError("Registration disappeared after provisioning")

            tenant = await self._build_tenant(registration)
            client = TelegramClient()
            client._handlers = self._handler_copy()
            client.set_runtime_context_factory(lambda tenant=tenant: tenant)
            logger.info(
                "Representative runtime starting | registration=%s bot_id=%s username=@%s handlers=%s",
                registration_id,
                tenant.bot_id,
                tenant.bot_username or "unknown",
                len(client._handlers),
            )
            try:
                await client.start(bot_token=reveal(registration["bot_token"]))
                me = await client.get_me()
                if int(me.id) != tenant.bot_id:
                    raise RuntimeError(f"Telegram bot id mismatch: expected {tenant.bot_id}, got {me.id}")
                with tenant_context(tenant):
                    await ensure_representative_panel(registration)
                runtime = RepresentativeRuntime(registration_id, tenant, client)
                register_telethon_client(client)
                runtime.task = asyncio.create_task(self._run(runtime), name=f"representative-bot-{registration_id}")
                self._runtimes[registration_id] = runtime
                await update_registration(registration_id, status="active", step="active", rejection_reason=None)
                logger.info(
                    "Representative runtime ACTIVE | registration=%s bot_id=%s username=@%s",
                    registration_id,
                    tenant.bot_id,
                    tenant.bot_username or "unknown",
                )
                return runtime
            except Exception as exc:
                logger.exception("Representative runtime failed | registration=%s", registration_id)
                await client.disconnect()
                await update_registration(
                    registration_id,
                    status="pending",
                    step="awaiting_admin",
                    rejection_reason=str(exc),
                )
                raise

    async def _run(self, runtime: RepresentativeRuntime) -> None:
        backoff = 2
        while not self._stopping:
            try:
                logger.info(
                    "Representative polling started | registration=%s bot_id=%s",
                    runtime.registration_id,
                    runtime.tenant.bot_id,
                )
                with client_context(runtime.client), tenant_context(runtime.tenant):
                    await runtime.client.run_until_disconnected()
                if self._stopping:
                    break
                logger.warning("Representative polling stopped; restarting | registration=%s", runtime.registration_id)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Representative polling crashed | registration=%s", runtime.registration_id)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def start_all(self) -> None:
        self._stopping = False
        registrations = await get_approved()
        logger.info("Representative registry scan | eligible=%s", len(registrations))
        for registration in registrations:
            rid = int(registration["id"])
            try:
                await self.start_for_registration(rid, provision=not bool(registration.get("tenant_db_name")))
            except Exception:
                logger.exception("Representative startup skipped | registration=%s", rid)
        logger.info("Representative registry scan complete | running=%s", len(self._runtimes))
        if self._supervisor_task is None or self._supervisor_task.done():
            self._supervisor_task = asyncio.create_task(self._supervise(), name="representative-runtime-supervisor")

    async def _supervise(self) -> None:
        """Recover active/approved registrations without requiring re-registration."""
        while not self._stopping:
            try:
                await asyncio.sleep(15)
                if self._stopping:
                    break
                registrations = await get_approved()
                eligible_ids = {int(row["id"]) for row in registrations}
                for registration in registrations:
                    rid = int(registration["id"])
                    runtime = self._runtimes.get(rid)
                    if runtime and runtime.client.is_connected() and runtime.task and not runtime.task.done():
                        continue
                    try:
                        await self.start_for_registration(
                            rid,
                            provision=not bool(registration.get("tenant_db_name")),
                        )
                    except Exception:
                        logger.exception("Representative supervisor retry failed | registration=%s", rid)

                for rid in list(self._runtimes):
                    if rid not in eligible_ids:
                        await self.stop_for_registration(rid)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Representative supervisor cycle failed")

    async def stop_for_registration(self, registration_id: int) -> None:
        async with self._lock(registration_id):
            runtime = self._runtimes.pop(registration_id, None)
            if not runtime:
                return
            unregister_telethon_client(runtime.client)
            if runtime.task and not runtime.task.done():
                runtime.task.cancel()
                await asyncio.gather(runtime.task, return_exceptions=True)
            await runtime.client.disconnect()
            logger.info("Representative runtime stopped | registration=%s", registration_id)

    async def stop_all(self) -> None:
        self._stopping = True
        if self._supervisor_task and not self._supervisor_task.done():
            self._supervisor_task.cancel()
            await asyncio.gather(self._supervisor_task, return_exceptions=True)
        self._supervisor_task = None
        await asyncio.gather(
            *(self.stop_for_registration(rid) for rid in list(self._runtimes)),
            return_exceptions=True,
        )

    def get_runtime(self, registration_id: int) -> RepresentativeRuntime | None:
        return self._runtimes.get(registration_id)


_manager: MultiBotManager | None = None


def get_multi_bot_manager() -> MultiBotManager | None:
    return _manager


async def start_multi_bot_manager(central_client: TelegramClient) -> MultiBotManager:
    global _manager
    _manager = MultiBotManager(central_client)
    await _manager.start_all()
    return _manager


async def stop_multi_bot_manager() -> None:
    global _manager
    if _manager is not None:
        await _manager.stop_all()
        _manager = None

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app import Kenzo
from app.custom_telethon import TelegramClient
from app.logger.telethon import register_telethon_client, unregister_telethon_client
from app.services.central_registry import get_approved, get_by_id, reveal, update_registration
from app.services.representative_bootstrap import ensure_representative_panel
from app.services.representative_provisioner import provision_representative, tenant_database_url
from app.runtime.context import TenantRuntime, tenant_context


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

    def _lock(self, registration_id: int) -> asyncio.Lock:
        return self._locks.setdefault(registration_id, asyncio.Lock())

    def _handler_copy(self):
        # Central registration handlers must never execute on representative bots.
        return [
            item for item in self.central_client._handlers
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
            if registration["status"] not in {"approved", "provisioning", "active"}:
                raise RuntimeError(f"Registration {registration_id} is not approved")

            if provision or not registration.get("tenant_db_name"):
                result = await provision_representative(registration_id)
                await update_registration(registration_id, **result)
                registration = await get_by_id(registration_id)

            tenant = await self._build_tenant(registration)
            client = TelegramClient()
            client._handlers = self._handler_copy()
            client.set_runtime_context_factory(lambda tenant=tenant: tenant)

            try:
                await client.start(bot_token=reveal(registration["bot_token"]))
                me = await client.get_me()
                if int(me.id) != tenant.bot_id:
                    raise RuntimeError(f"Telegram bot id mismatch: expected {tenant.bot_id}, got {me.id}")

                # All DB and Redis operations below are automatically isolated to
                # this registration's tenant context.
                with tenant_context(tenant):
                    await ensure_representative_panel(registration)

                runtime = RepresentativeRuntime(registration_id, tenant, client)
                register_telethon_client(client)
                runtime.task = asyncio.create_task(self._run(runtime), name=f"representative-bot-{registration_id}")
                self._runtimes[registration_id] = runtime
                await update_registration(registration_id, status="active", step="active", rejection_reason=None)
                return runtime
            except Exception:
                await client.disconnect()
                await update_registration(registration_id, status="pending", step="awaiting_admin", rejection_reason="bot activation failed")
                raise

    async def _run(self, runtime: RepresentativeRuntime) -> None:
        backoff = 2
        while not self._stopping:
            try:
                await runtime.client.run_until_disconnected()
                if self._stopping:
                    break
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def start_all(self) -> None:
        self._stopping = False
        registrations = await get_approved()
        for registration in registrations:
            try:
                await self.start_for_registration(int(registration["id"]), provision=not bool(registration.get("tenant_db_name")))
            except Exception:
                # One broken representative must never prevent other bots from starting.
                continue

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

    async def stop_all(self) -> None:
        self._stopping = True
        ids = list(self._runtimes)
        await asyncio.gather(*(self.stop_for_registration(rid) for rid in ids), return_exceptions=True)

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

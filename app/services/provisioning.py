from __future__ import annotations

from dataclasses import dataclass
import traceback

from app.db.models import RegistrationStatus
from app.db.session import SessionFactory
from app.services.registration_store import RegistrationStore
from app.services.secrets import get_secret_box
from app.services.tenant import TenantService
from app.telegram.representative.registry import registry


@dataclass(slots=True)
class ProvisionResult:
    registration_id: int
    tenant_id: str
    bot_username: str | None


class ProvisioningService:
    """C-04 lifecycle: registration -> tenant -> live representative bot -> active."""

    def __init__(self) -> None:
        self.registrations = RegistrationStore()
        self.tenants = TenantService()

    async def provision(self, registration_id: int) -> ProvisionResult:
        print(f"[provisioning] START registration={registration_id}", flush=True)
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        record = await self.registrations.get(registration_id)
        if record is None:
            raise LookupError("registration not found")
        print(
            f"[provisioning] registration={record.id} status={record.status} bot_id={record.bot_id} "
            f"panel_url={record.panel_url!r}",
            flush=True,
        )
        if record.status not in (RegistrationStatus.PROVISIONING.value, RegistrationStatus.FAILED.value):
            if record.status == RegistrationStatus.ACTIVE.value and record.tenant_id:
                tenant = await self.tenants.get_by_registration(record.id)
                if tenant:
                    return ProvisionResult(record.id, tenant.id, tenant.bot_username)
            raise RuntimeError(f"registration is not provisionable: {record.status}")
        required = {
            "brand": record.brand,
            "bot_id": record.bot_id,
            "bot_token_encrypted": record.bot_token_encrypted,
            "panel_url": record.panel_url,
            "panel_api_key_encrypted": record.panel_api_key_encrypted,
        }
        missing = [name for name, value in required.items() if value in (None, "")]
        if missing:
            await self.registrations.mark_failed(record.id, "Missing provisioning fields: " + ", ".join(missing))
            raise RuntimeError("registration has incomplete provisioning data")

        box = get_secret_box()
        bot_token = box.decrypt(record.bot_token_encrypted)
        panel_api_key = box.decrypt(record.panel_api_key_encrypted)
        tenant = None
        try:
            print(f"[provisioning] creating/updating tenant registration={record.id}", flush=True)
            tenant = await self.tenants.provision(
                registration_id=record.id,
                owner_id=record.owner_id,
                brand=record.brand or "نمایندگی",
                bot_id=record.bot_id,
                bot_username=None,
                bot_token=bot_token,
                panel_url=record.panel_url,
                panel_username=record.panel_username,
                panel_api_key=panel_api_key,
            )
            print(f"[provisioning] tenant ready tenant={tenant.id}; starting Telegram runtime", flush=True)
            runtime = await registry.start(tenant.id, bot_token)
            print(f"[provisioning] Telegram runtime started tenant={tenant.id}", flush=True)
            me = await runtime.client.get_me()
            username = getattr(me, "username", None)
            print(f"[provisioning] Telegram getMe OK tenant={tenant.id} username={username!r}", flush=True)
            tenant = await self.tenants.update_bot_username(tenant.id, username)
            await self.tenants.activate(tenant.id)
            await self.registrations.mark_active(record.id, tenant.id)
            print(f"[provisioning] ACTIVE registration={record.id} tenant={tenant.id}", flush=True)
            return ProvisionResult(record.id, tenant.id, username)
        except Exception as exc:
            print(
                f"[provisioning] FAILED registration={record.id} tenant={getattr(tenant, 'id', None)} "
                f"error={type(exc).__name__}: {exc}",
                flush=True,
            )
            traceback.print_exc()
            if tenant is not None:
                try:
                    await self.tenants.fail(tenant.id)
                    await registry.stop(tenant.id)
                except Exception as cleanup_exc:
                    print(f"[provisioning] cleanup failed tenant={tenant.id}: {type(cleanup_exc).__name__}: {cleanup_exc}", flush=True)
            await self.registrations.mark_failed(record.id, f"Provisioning failed: {type(exc).__name__}")
            raise

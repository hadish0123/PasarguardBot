from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select

from app.db.models import TenantRecord, TenantStatus
from app.db.session import SessionFactory
from app.services.secrets import get_secret_box


@dataclass(slots=True)
class Tenant:
    id: str
    owner_id: int
    brand: str
    bot_id: int
    bot_username: str | None
    panel_url: str
    status: str


@dataclass(frozen=True, slots=True)
class RuntimeTenant:
    id: str
    bot_token: str


class TenantService:
    """Persistent tenant lifecycle with idempotent provisioning."""

    async def provision(self, registration_id: int, owner_id: int, brand: str, bot_id: int,
                        bot_username: str | None, bot_token: str, panel_url: str,
                        panel_username: str | None, panel_api_key: str) -> Tenant:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            existing = await session.scalar(select(TenantRecord).where(TenantRecord.registration_id == registration_id))
            box = get_secret_box()
            if existing is None:
                existing = TenantRecord(
                    id=f"tenant_{uuid4().hex}", registration_id=registration_id, owner_id=owner_id,
                    brand=brand, bot_id=bot_id, bot_username=bot_username,
                    bot_token_encrypted=box.encrypt(bot_token), panel_url=panel_url,
                    panel_username=panel_username, panel_api_key_encrypted=box.encrypt(panel_api_key),
                    status=TenantStatus.PROVISIONING.value,
                )
                session.add(existing)
            else:
                existing.owner_id = owner_id
                existing.brand = brand
                existing.bot_id = bot_id
                existing.bot_username = bot_username
                existing.bot_token_encrypted = box.encrypt(bot_token)
                existing.panel_url = panel_url
                existing.panel_username = panel_username
                existing.panel_api_key_encrypted = box.encrypt(panel_api_key)
                if existing.status == TenantStatus.FAILED.value:
                    existing.status = TenantStatus.PROVISIONING.value
            await session.commit()
            await session.refresh(existing)
            return self._to_domain(existing)

    async def update_bot_username(self, tenant_id: str, username: str | None) -> Tenant:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(TenantRecord, tenant_id)
            if record is None:
                raise LookupError("tenant not found")
            record.bot_username = username
            await session.commit()
            await session.refresh(record)
            return self._to_domain(record)

    async def get_by_registration(self, registration_id: int) -> Tenant | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.scalar(select(TenantRecord).where(TenantRecord.registration_id == registration_id))
            return self._to_domain(record) if record else None

    async def list_runtime_tenants(self, excluded_bot_token: str | None = None) -> list[RuntimeTenant]:
        """Return active tenant runtimes, excluding the central bot token."""
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        box = get_secret_box()
        excluded = (excluded_bot_token or "").strip()
        async with SessionFactory() as session:
            rows = list((await session.execute(
                select(TenantRecord).where(TenantRecord.status == TenantStatus.ACTIVE.value)
            )).scalars().all())
        tenants: list[RuntimeTenant] = []
        for record in rows:
            if not record.bot_token_encrypted:
                continue
            try:
                token = box.decrypt(record.bot_token_encrypted).strip()
            except Exception:
                continue
            if not token or (excluded and token == excluded):
                continue
            tenants.append(RuntimeTenant(record.id, token))
        return tenants

    async def set_status(self, tenant_id: str, status: TenantStatus) -> Tenant:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(TenantRecord, tenant_id)
            if record is None:
                raise LookupError("tenant not found")
            record.status = status.value
            await session.commit()
            await session.refresh(record)
            return self._to_domain(record)

    async def activate(self, tenant_id: str) -> Tenant:
        return await self.set_status(tenant_id, TenantStatus.ACTIVE)

    async def suspend(self, tenant_id: str) -> Tenant:
        return await self.set_status(tenant_id, TenantStatus.SUSPENDED)

    async def fail(self, tenant_id: str) -> Tenant:
        return await self.set_status(tenant_id, TenantStatus.FAILED)

    @staticmethod
    def _to_domain(record: TenantRecord) -> Tenant:
        return Tenant(record.id, record.owner_id, record.brand, record.bot_id, record.bot_username, record.panel_url, record.status)

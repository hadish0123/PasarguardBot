from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import PermissionDenied
from app.core.config import settings
from app.db.models import RegistrationStatus, RepresentativeRegistration, TenantRecord, TenantStatus
from app.db.session import SessionFactory
from app.services.secrets import get_secret_box


class CentralAdminService:
    """Central-only authorization and registration/tenant management boundary."""

    @staticmethod
    def is_admin(user_id: int) -> bool:
        return user_id in settings.admin_ids

    @classmethod
    def require_admin(cls, user_id: int) -> None:
        if not cls.is_admin(user_id):
            raise PermissionDenied("central admin permission required")

    async def pending(self) -> list[RepresentativeRegistration]:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(
                select(RepresentativeRegistration)
                .where(RepresentativeRegistration.status == RegistrationStatus.PENDING.value)
                .order_by(RepresentativeRegistration.id.asc())
            )
            return list(result.scalars().all())

    async def get(self, registration_id: int) -> RepresentativeRegistration | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.get(RepresentativeRegistration, registration_id)

    async def approve(self, registration_id: int) -> RepresentativeRegistration:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(RepresentativeRegistration, registration_id)
            if record is None:
                raise LookupError("registration not found")
            if record.status != RegistrationStatus.PENDING.value:
                raise ValueError("registration is not pending")
            record.status = RegistrationStatus.PROVISIONING.value
            await session.commit()
            await session.refresh(record)
            return record

    async def reject(self, registration_id: int, reason: str) -> RepresentativeRegistration:
        reason = reason.strip()
        if len(reason) < 3:
            raise ValueError("rejection reason is required")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(RepresentativeRegistration, registration_id)
            if record is None:
                raise LookupError("registration not found")
            if record.status != RegistrationStatus.PENDING.value:
                raise ValueError("registration is not pending")
            record.status = RegistrationStatus.REJECTED.value
            record.rejection_reason = reason[:2000]
            await session.commit()
            await session.refresh(record)
            return record

    async def tenants(self) -> list[TenantRecord]:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(select(TenantRecord).order_by(TenantRecord.id.asc()))
            return list(result.scalars().all())

    async def get_tenant(self, tenant_id: str) -> TenantRecord | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(TenantRecord, tenant_id)
            if record is not None:
                return record
            if tenant_id.isdigit():
                return await session.scalar(select(TenantRecord).where(TenantRecord.bot_id == int(tenant_id)))
            return None

    async def get_tenant_by_bot_id(self, bot_id: int) -> TenantRecord | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.scalar(select(TenantRecord).where(TenantRecord.bot_id == bot_id))

    async def _get_tenant_in_session(self, session, tenant_id: str) -> TenantRecord | None:
        record = await session.get(TenantRecord, tenant_id)
        if record is not None:
            return record
        if tenant_id.isdigit():
            return await session.scalar(select(TenantRecord).where(TenantRecord.bot_id == int(tenant_id)))
        return None

    async def set_tenant_status(self, tenant_id: str, status: TenantStatus) -> TenantRecord:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await self._get_tenant_in_session(session, tenant_id)
            if record is None:
                raise LookupError("tenant not found")
            record.status = status.value
            await session.commit()
            await session.refresh(record)
            return record

    async def change_tenant_owner(self, tenant_id: str, owner_id: int) -> TenantRecord:
        if owner_id <= 0:
            raise ValueError("invalid owner id")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await self._get_tenant_in_session(session, tenant_id)
            if record is None:
                raise LookupError("tenant not found")
            record.owner_id = owner_id
            registration = await session.scalar(
                select(RepresentativeRegistration).where(RepresentativeRegistration.id == record.registration_id)
            )
            if registration is not None:
                registration.owner_id = owner_id
            await session.commit()
            await session.refresh(record)
            return record

    async def delete_tenant(self, tenant_id: str) -> TenantRecord:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await self._get_tenant_in_session(session, tenant_id)
            if record is None:
                raise LookupError("tenant not found")
            await session.delete(record)
            await session.commit()
            return record

    async def get_tenant_bot_token(self, tenant_id: str) -> str:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await self._get_tenant_in_session(session, tenant_id)
            if record is None or not record.bot_token_encrypted:
                raise LookupError("bot token not found")
            encrypted = record.bot_token_encrypted
        return get_secret_box().decrypt(encrypted).strip()

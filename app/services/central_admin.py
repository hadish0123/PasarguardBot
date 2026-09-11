from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import PermissionDenied
from app.core.config import settings
from app.db.models import RegistrationStatus, RepresentativeRegistration
from app.db.session import SessionFactory


class CentralAdminService:
    """Central-only authorization and registration approval boundary."""

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

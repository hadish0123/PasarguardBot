from __future__ import annotations

import secrets
import string

from sqlalchemy import select

from app.db.models import RegistrationStatus, RegistrationStep, RepresentativeRegistration
from app.db.session import SessionFactory


_ALPHABET = string.ascii_uppercase + string.digits


def new_tracking_code() -> str:
    return "PG-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


class RegistrationStore:
    """Persistence boundary for central representative registration records."""

    async def create_or_resume_draft(self, owner_id: int) -> RepresentativeRegistration:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(
                select(RepresentativeRegistration)
                .where(
                    RepresentativeRegistration.owner_id == owner_id,
                    RepresentativeRegistration.status.in_(
                        (RegistrationStatus.DRAFT.value, RegistrationStatus.PENDING.value, RegistrationStatus.PROVISIONING.value)
                    ),
                )
                .order_by(RepresentativeRegistration.id.desc()).limit(1)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing
            record = RepresentativeRegistration(owner_id=owner_id, tracking_code=new_tracking_code())
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def create_draft(self, owner_id: int) -> RepresentativeRegistration:
        return await self.create_or_resume_draft(owner_id)

    async def get_by_tracking_code(self, owner_id: int, tracking_code: str) -> RepresentativeRegistration | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(select(RepresentativeRegistration).where(
                RepresentativeRegistration.owner_id == owner_id,
                RepresentativeRegistration.tracking_code == tracking_code.strip().upper(),
            ))
            return result.scalar_one_or_none()

    async def latest_for_owner(self, owner_id: int) -> RepresentativeRegistration | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(select(RepresentativeRegistration)
                .where(RepresentativeRegistration.owner_id == owner_id)
                .order_by(RepresentativeRegistration.id.desc()).limit(1))
            return result.scalar_one_or_none()

    async def get(self, record_id: int) -> RepresentativeRegistration | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.get(RepresentativeRegistration, record_id)

    async def update(self, record_id: int, **values) -> RepresentativeRegistration:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(RepresentativeRegistration, record_id)
            if record is None:
                raise LookupError("registration not found")
            for key, value in values.items():
                setattr(record, key, value)
            await session.commit()
            await session.refresh(record)
            return record

    async def set_step(self, record_id: int, step: RegistrationStep) -> None:
        await self.update(record_id, step=step.value)

    async def mark_pending(self, record_id: int) -> None:
        await self.update(record_id, status=RegistrationStatus.PENDING.value, step=RegistrationStep.COMPLETE.value)

    async def mark_provisioning(self, record_id: int) -> None:
        await self.update(record_id, status=RegistrationStatus.PROVISIONING.value)

    async def mark_active(self, record_id: int, tenant_id: str) -> None:
        await self.update(record_id, status=RegistrationStatus.ACTIVE.value, tenant_id=tenant_id)

    async def mark_failed(self, record_id: int, reason: str) -> None:
        await self.update(record_id, status=RegistrationStatus.FAILED.value, rejection_reason=reason[:2000])

    async def mark_rejected(self, record_id: int, reason: str | None = None) -> None:
        await self.update(record_id, status=RegistrationStatus.REJECTED.value, rejection_reason=reason)

from __future__ import annotations

import secrets
import string

from sqlalchemy import select

from app.db.models import RegistrationStatus, RepresentativeRegistration
from app.db.session import SessionFactory


_ALPHABET = string.ascii_uppercase + string.digits


def new_tracking_code() -> str:
    return "PG-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


class RegistrationStore:
    """Persistence boundary for central representative registration records."""

    async def create_draft(self, owner_id: int) -> RepresentativeRegistration:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = RepresentativeRegistration(owner_id=owner_id, tracking_code=new_tracking_code())
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def get_by_tracking_code(self, owner_id: int, tracking_code: str) -> RepresentativeRegistration | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(
                select(RepresentativeRegistration).where(
                    RepresentativeRegistration.owner_id == owner_id,
                    RepresentativeRegistration.tracking_code == tracking_code.strip().upper(),
                )
            )
            return result.scalar_one_or_none()

    async def latest_for_owner(self, owner_id: int) -> RepresentativeRegistration | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(
                select(RepresentativeRegistration)
                .where(RepresentativeRegistration.owner_id == owner_id)
                .order_by(RepresentativeRegistration.id.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def mark_pending(self, record_id: int) -> None:
        await self._set_status(record_id, RegistrationStatus.PENDING.value)

    async def mark_active(self, record_id: int) -> None:
        await self._set_status(record_id, RegistrationStatus.ACTIVE.value)

    async def mark_rejected(self, record_id: int, reason: str | None = None) -> None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(RepresentativeRegistration, record_id)
            if record is None:
                return
            record.status = RegistrationStatus.REJECTED.value
            record.rejection_reason = reason
            await session.commit()

    async def _set_status(self, record_id: int, status: str) -> None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(RepresentativeRegistration, record_id)
            if record is None:
                return
            record.status = status
            await session.commit()

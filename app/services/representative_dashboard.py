from __future__ import annotations

from sqlalchemy import select

from app.db.models import TenantRecord, TenantStatus
from app.db.session import SessionFactory
from app.runtime.context import require_tenant


class RepresentativeDashboardService:
    """Tenant-scoped read model for the representative admin home."""

    async def tenant(self) -> TenantRecord:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        tenant_id = require_tenant()
        async with SessionFactory() as session:
            record = await session.scalar(select(TenantRecord).where(TenantRecord.id == tenant_id))
            if record is None:
                raise LookupError("tenant not found")
            return record

    async def is_owner(self, user_id: int) -> bool:
        record = await self.tenant()
        return record.owner_id == user_id and record.status == TenantStatus.ACTIVE.value

    async def snapshot(self) -> dict[str, object]:
        record = await self.tenant()
        return {
            "brand": record.brand,
            "bot_username": record.bot_username,
            "owner_id": record.owner_id,
            "status": record.status,
            "panel_url": record.panel_url,
        }

from __future__ import annotations

from sqlalchemy import select
from app.db.models import RepresentativeLog
from app.db.session import SessionFactory
from app.runtime.context import require_tenant


class LogService:
    async def add(self, action: str, details: str = "", actor_id: int | None = None):
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            row = RepresentativeLog(
                tenant_id=require_tenant(),
                actor_id=actor_id,
                action=action.strip()[:120],
                details=details.strip()[:1000],
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def list(self, limit: int = 30, offset: int = 0):
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        async with SessionFactory() as session:
            result = await session.execute(
                select(RepresentativeLog)
                .where(RepresentativeLog.tenant_id == require_tenant())
                .order_by(RepresentativeLog.id.desc())
                .offset(offset)
                .limit(limit + 1)
            )
            rows = list(result.scalars().all())
            return rows[:limit], len(rows) > limit


SERVICE = LogService()

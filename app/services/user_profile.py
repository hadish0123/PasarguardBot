from __future__ import annotations

from sqlalchemy import select

from app.db.models import RepresentativeUser
from app.db.session import SessionFactory
from app.runtime.context import require_tenant


class UserProfileService:
    async def get(self, telegram_user_id: int) -> RepresentativeUser | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        tenant_id = require_tenant()
        async with SessionFactory() as session:
            return await session.scalar(select(RepresentativeUser).where(RepresentativeUser.tenant_id == tenant_id, RepresentativeUser.telegram_user_id == telegram_user_id))

    async def update_name(self, telegram_user_id: int, first_name: str, last_name: str | None = None) -> RepresentativeUser:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        first_name = first_name.strip()[:120]
        last_name = (last_name or "").strip()[:120] or None
        if not first_name:
            raise ValueError("first_name is required")
        tenant_id = require_tenant()
        async with SessionFactory() as session:
            user = await session.scalar(select(RepresentativeUser).where(RepresentativeUser.tenant_id == tenant_id, RepresentativeUser.telegram_user_id == telegram_user_id))
            if user is None:
                raise LookupError("user not found")
            user.first_name = first_name
            user.last_name = last_name
            await session.commit()
            await session.refresh(user)
            return user


SERVICE = UserProfileService()

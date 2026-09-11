from __future__ import annotations

from sqlalchemy import select

from app.db.models import RepresentativeUser, UserBalanceLog
from app.db.session import SessionFactory
from app.runtime.context import require_tenant


class UserWalletService:
    async def _user(self, telegram_user_id: int) -> RepresentativeUser | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        tenant_id = require_tenant()
        async with SessionFactory() as session:
            return await session.scalar(select(RepresentativeUser).where(
                RepresentativeUser.tenant_id == tenant_id,
                RepresentativeUser.telegram_user_id == telegram_user_id,
            ))

    async def balance(self, telegram_user_id: int) -> float:
        user = await self._user(telegram_user_id)
        return float(user.balance) if user else 0.0

    async def transactions(self, telegram_user_id: int, limit: int = 15) -> list[UserBalanceLog]:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        tenant_id = require_tenant()
        async with SessionFactory() as session:
            user = await session.scalar(select(RepresentativeUser).where(
                RepresentativeUser.tenant_id == tenant_id,
                RepresentativeUser.telegram_user_id == telegram_user_id,
            ))
            if user is None:
                return []
            result = await session.execute(
                select(UserBalanceLog)
                .where(UserBalanceLog.tenant_id == tenant_id, UserBalanceLog.user_id == user.id)
                .order_by(UserBalanceLog.id.desc())
                .limit(max(1, min(limit, 50)))
            )
            return list(result.scalars().all())


SERVICE = UserWalletService()

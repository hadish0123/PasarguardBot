from __future__ import annotations

from sqlalchemy import select

from app.db.models import Order, RepresentativeUser, ServiceSubscription
from app.db.session import SessionFactory
from app.runtime.context import require_tenant


class UserServicesService:
    async def current_user(self, telegram_user_id: int) -> RepresentativeUser | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.scalar(select(RepresentativeUser).where(RepresentativeUser.tenant_id == require_tenant(), RepresentativeUser.telegram_user_id == telegram_user_id))

    async def orders(self, telegram_user_id: int, limit: int = 20) -> list[Order]:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(select(Order).where(Order.tenant_id == require_tenant(), Order.telegram_user_id == telegram_user_id).order_by(Order.id.desc()).limit(max(1, min(limit, 50))))
            return list(result.scalars().all())

    async def subscriptions(self, telegram_user_id: int, limit: int = 20) -> list[ServiceSubscription]:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(select(ServiceSubscription).where(ServiceSubscription.tenant_id == require_tenant(), ServiceSubscription.telegram_user_id == telegram_user_id).order_by(ServiceSubscription.id.desc()).limit(max(1, min(limit, 50))))
            return list(result.scalars().all())

    async def subscription(self, telegram_user_id: int, subscription_id: int) -> ServiceSubscription | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.scalar(select(ServiceSubscription).where(ServiceSubscription.id == subscription_id, ServiceSubscription.tenant_id == require_tenant(), ServiceSubscription.telegram_user_id == telegram_user_id))


SERVICE = UserServicesService()

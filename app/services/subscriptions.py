from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Order, ServiceSubscription
from app.db.session import AsyncSessionLocal
from app.runtime.context import require_tenant
from app.services.logs import SERVICE as LOG_SERVICE


class SubscriptionService:
    async def _expire_due(self, db, tenant: str) -> int:
        now = datetime.now(timezone.utc)
        rows = list(
            (
                await db.execute(
                    select(ServiceSubscription).where(
                        ServiceSubscription.tenant_id == tenant,
                        ServiceSubscription.status == "active",
                        ServiceSubscription.expires_at.is_not(None),
                        ServiceSubscription.expires_at <= now,
                    )
                )
            ).scalars().all()
        )
        for item in rows:
            item.status = "expired"
        if rows:
            await db.commit()
        return len(rows)

    async def list_for_tenant(self, limit: int = 100):
        tenant = require_tenant()
        async with AsyncSessionLocal() as db:
            await self._expire_due(db, tenant)
            stmt = select(ServiceSubscription).where(ServiceSubscription.tenant_id == tenant).order_by(ServiceSubscription.id.desc()).limit(min(max(limit, 1), 100))
            return list((await db.execute(stmt)).scalars().all())

    async def list_for_user(self, telegram_user_id: int, limit: int = 30):
        tenant = require_tenant()
        async with AsyncSessionLocal() as db:
            await self._expire_due(db, tenant)
            stmt = select(ServiceSubscription).where(ServiceSubscription.tenant_id == tenant, ServiceSubscription.telegram_user_id == telegram_user_id).order_by(ServiceSubscription.id.desc()).limit(min(max(limit, 1), 100))
            return list((await db.execute(stmt)).scalars().all())

    async def get_by_order(self, order_id: int):
        tenant = require_tenant()
        async with AsyncSessionLocal() as db:
            await self._expire_due(db, tenant)
            return await db.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id == tenant, ServiceSubscription.order_id == order_id))

    async def get(self, subscription_id: int):
        tenant = require_tenant()
        async with AsyncSessionLocal() as db:
            await self._expire_due(db, tenant)
            return await db.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id == tenant, ServiceSubscription.id == subscription_id))

    async def get_for_user(self, subscription_id: int, telegram_user_id: int):
        tenant = require_tenant()
        async with AsyncSessionLocal() as db:
            await self._expire_due(db, tenant)
            return await db.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id == tenant, ServiceSubscription.id == subscription_id, ServiceSubscription.telegram_user_id == telegram_user_id))

    async def ensure_for_paid_order(self, order_id: int):
        tenant = require_tenant()
        async with AsyncSessionLocal() as db:
            order = await db.scalar(select(Order).where(Order.tenant_id == tenant, Order.id == order_id))
            if order is None:
                raise LookupError("سفارش پیدا نشد.")
            if order.status != "paid":
                raise ValueError("فقط سفارش پرداخت‌شده قابل تحویل است.")
            existing = await db.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id == tenant, ServiceSubscription.order_id == order.id))
            if existing:
                return existing
            item = ServiceSubscription(tenant_id=tenant, order_id=order.id, telegram_user_id=order.telegram_user_id, plan_id=order.plan_id, plan_name=order.plan_name, volume_gb=order.volume_gb, days=order.days, status="pending_provisioning", provider="pasarguard")
            db.add(item)
            await db.commit()
            await db.refresh(item)
            return item

    async def mark_provisioning(self, order_id: int):
        item = await self.ensure_for_paid_order(order_id)
        if item.status == "active":
            return item
        async with AsyncSessionLocal() as db:
            item = await db.merge(item)
            item.status = "provisioning"
            await db.commit()
            await db.refresh(item)
            return item

    async def mark_active(self, order_id: int, provider_service_id: str | None = None, subscription_url: str | None = None, starts_at: datetime | None = None, expires_at: datetime | None = None):
        item = await self.ensure_for_paid_order(order_id)
        async with AsyncSessionLocal() as db:
            item = await db.merge(item)
            item.status = "active"
            item.provider_service_id = provider_service_id
            item.subscription_url = subscription_url
            item.starts_at = starts_at or datetime.now(timezone.utc)
            item.expires_at = expires_at
            await db.commit()
            await db.refresh(item)
            return item

    async def revoke(self, subscription_id: int, actor_id: int | None = None):
        tenant = require_tenant()
        async with AsyncSessionLocal() as db:
            item = await db.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id == tenant, ServiceSubscription.id == subscription_id))
            if item is None:
                raise LookupError("سرویس پیدا نشد.")
            if item.status == "revoked":
                return item
            item.status = "revoked"
            await db.commit()
            await db.refresh(item)
        await LOG_SERVICE.add("subscription.revoked", f"subscription=#{subscription_id}", actor_id)
        return item

    async def mark_expired(self, subscription_id: int | None = None):
        tenant = require_tenant()
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            if subscription_id is not None:
                item = await db.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id == tenant, ServiceSubscription.id == subscription_id))
                if item is None:
                    raise LookupError("سرویس پیدا نشد.")
                if item.status != "active" or not item.expires_at or item.expires_at > now:
                    raise ValueError("این سرویس هنوز منقضی نشده است.")
                rows = [item]
            else:
                rows = list((await db.execute(select(ServiceSubscription).where(ServiceSubscription.tenant_id == tenant, ServiceSubscription.status == "active", ServiceSubscription.expires_at.is_not(None), ServiceSubscription.expires_at <= now))).scalars().all())
            for item in rows:
                item.status = "expired"
            if rows:
                await db.commit()
                for item in rows:
                    await db.refresh(item)
            return rows[0] if subscription_id is not None else rows


SERVICE = SubscriptionService()

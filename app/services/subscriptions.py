from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.db.models import Order, ServiceSubscription
from app.db.session import AsyncSessionLocal
from app.runtime.context import require_tenant

class SubscriptionService:
    async def list_for_user(self, telegram_user_id:int, limit:int=30):
        tenant=require_tenant()
        async with AsyncSessionLocal() as db:
            stmt=select(ServiceSubscription).where(ServiceSubscription.tenant_id==tenant,ServiceSubscription.telegram_user_id==telegram_user_id).order_by(ServiceSubscription.id.desc()).limit(limit)
            return list((await db.execute(stmt)).scalars().all())
    async def get_by_order(self, order_id:int):
        tenant=require_tenant()
        async with AsyncSessionLocal() as db:
            return await db.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id==tenant,ServiceSubscription.order_id==order_id))
    async def ensure_for_paid_order(self, order_id:int):
        tenant=require_tenant()
        async with AsyncSessionLocal() as db:
            order=await db.scalar(select(Order).where(Order.tenant_id==tenant,Order.id==order_id))
            if order is None: raise LookupError("سفارش پیدا نشد.")
            if order.status != "paid": raise ValueError("فقط سفارش پرداخت‌شده قابل تحویل است.")
            existing=await db.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id==tenant,ServiceSubscription.order_id==order.id))
            if existing:return existing
            item=ServiceSubscription(tenant_id=tenant,order_id=order.id,telegram_user_id=order.telegram_user_id,plan_id=order.plan_id,plan_name=order.plan_name,volume_gb=order.volume_gb,days=order.days,status="pending_provisioning",provider="pasarguard")
            db.add(item);await db.commit();await db.refresh(item);return item
    async def mark_provisioning(self, order_id:int):
        item=await self.ensure_for_paid_order(order_id)
        async with AsyncSessionLocal() as db:
            item=await db.merge(item);item.status="provisioning";await db.commit();await db.refresh(item);return item
    async def mark_active(self, order_id:int, provider_service_id:str|None=None):
        item=await self.ensure_for_paid_order(order_id)
        now=datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            item=await db.merge(item);item.status="active";item.provider_service_id=provider_service_id;item.starts_at=now;item.expires_at=now+timedelta(days=item.days);await db.commit();await db.refresh(item);return item
    async def revoke(self, subscription_id:int):
        tenant=require_tenant()
        async with AsyncSessionLocal() as db:
            item=await db.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id==tenant,ServiceSubscription.id==subscription_id))
            if item is None:raise LookupError("سرویس پیدا نشد.")
            item.status="revoked";await db.commit();await db.refresh(item);return item
SERVICE=SubscriptionService()

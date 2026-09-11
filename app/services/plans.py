from __future__ import annotations

from sqlalchemy import select

from app.db.models import Order, Plan, ServiceSubscription
from app.db.session import SessionFactory
from app.runtime.context import require_tenant


class PlanService:
    async def list(self) -> list[Plan]:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(
                select(Plan).where(Plan.tenant_id == require_tenant()).order_by(Plan.id.desc())
            )
            return list(result.scalars().all())

    @staticmethod
    def _validate(name: str, volume_gb: float, days: int, price: float, provider_template_id: int | None) -> str:
        name = name.strip()
        if not 2 <= len(name) <= 120:
            raise ValueError("نام پلن باید بین 2 تا 120 کاراکتر باشد.")
        if volume_gb <= 0:
            raise ValueError("حجم باید بیشتر از صفر باشد.")
        if days <= 0:
            raise ValueError("مدت باید بیشتر از صفر باشد.")
        if price < 0:
            raise ValueError("قیمت نمی‌تواند منفی باشد.")
        if provider_template_id is not None and provider_template_id <= 0:
            raise ValueError("شناسه Template پاسارگارد نامعتبر است.")
        return name

    async def create(self, name: str, volume_gb: float, days: int, price: float, provider_template_id: int | None = None) -> Plan:
        name = self._validate(name, volume_gb, days, price, provider_template_id)
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            plan = Plan(
                tenant_id=require_tenant(), name=name, volume_gb=volume_gb,
                days=days, price=price, enabled=True,
                provider_template_id=provider_template_id,
            )
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            return plan

    async def get(self, plan_id: int) -> Plan | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.scalar(
                select(Plan).where(Plan.id == plan_id, Plan.tenant_id == require_tenant())
            )

    async def update(self, plan_id: int, *, name: str, volume_gb: float, days: int,
                     price: float, provider_template_id: int | None) -> Plan:
        name = self._validate(name, volume_gb, days, price, provider_template_id)
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            plan = await session.scalar(
                select(Plan).where(Plan.id == plan_id, Plan.tenant_id == require_tenant())
            )
            if plan is None:
                raise LookupError("پلن پیدا نشد.")
            plan.name = name
            plan.volume_gb = volume_gb
            plan.days = days
            plan.price = price
            plan.provider_template_id = provider_template_id
            await session.commit()
            await session.refresh(plan)
            return plan

    async def toggle(self, plan_id: int) -> Plan:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            plan = await session.scalar(
                select(Plan).where(Plan.id == plan_id, Plan.tenant_id == require_tenant())
            )
            if plan is None:
                raise LookupError("پلن پیدا نشد.")
            plan.enabled = not plan.enabled
            await session.commit()
            await session.refresh(plan)
            return plan

    async def delete(self, plan_id: int) -> None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        tenant_id = require_tenant()
        async with SessionFactory() as session:
            plan = await session.scalar(
                select(Plan).where(Plan.id == plan_id, Plan.tenant_id == tenant_id)
            )
            if plan is None:
                raise LookupError("پلن پیدا نشد.")
            order_exists = await session.scalar(
                select(Order.id).where(Order.tenant_id == tenant_id, Order.plan_id == plan_id).limit(1)
            )
            subscription_exists = await session.scalar(
                select(ServiceSubscription.id).where(
                    ServiceSubscription.tenant_id == tenant_id,
                    ServiceSubscription.plan_id == plan_id,
                ).limit(1)
            )
            if order_exists is not None or subscription_exists is not None:
                raise ValueError("این پلن سابقه سفارش یا سرویس دارد و قابل حذف نیست؛ آن را غیرفعال کنید.")
            await session.delete(plan)
            await session.commit()


SERVICE = PlanService()

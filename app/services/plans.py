from __future__ import annotations

from sqlalchemy import delete, select

from app.db.models import Plan
from app.db.session import SessionFactory
from app.runtime.context import require_tenant


class PlanService:
    async def list(self) -> list[Plan]:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(select(Plan).where(Plan.tenant_id == require_tenant()).order_by(Plan.id.desc()))
            return list(result.scalars().all())

    async def create(self, name: str, volume_gb: float, days: int, price: float, provider_template_id: int | None = None) -> Plan:
        if not name.strip() or volume_gb <= 0 or days <= 0 or price < 0:
            raise ValueError("invalid plan values")
        if provider_template_id is not None and provider_template_id <= 0:
            raise ValueError("invalid provider template id")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            plan = Plan(tenant_id=require_tenant(), name=name.strip()[:120], volume_gb=volume_gb, days=days, price=price, enabled=True, provider_template_id=provider_template_id)
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            return plan

    async def get(self, plan_id: int) -> Plan | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.scalar(select(Plan).where(Plan.id == plan_id, Plan.tenant_id == require_tenant()))

    async def toggle(self, plan_id: int) -> Plan:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            plan = await session.scalar(select(Plan).where(Plan.id == plan_id, Plan.tenant_id == require_tenant()))
            if plan is None:
                raise LookupError("plan not found")
            plan.enabled = not plan.enabled
            await session.commit()
            await session.refresh(plan)
            return plan

    async def delete(self, plan_id: int) -> None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            plan = await session.scalar(select(Plan).where(Plan.id == plan_id, Plan.tenant_id == require_tenant()))
            if plan is None:
                raise LookupError("plan not found")
            await session.delete(plan)
            await session.commit()

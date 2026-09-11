from __future__ import annotations
from sqlalchemy import select
from app.db.models import Plan, TrialClaim
from app.db.session import AsyncSessionLocal
from app.runtime.context import require_tenant
class TrialService:
    async def claim(self,telegram_user_id:int):
        tenant_id=require_tenant()
        async with AsyncSessionLocal() as db:
            old=await db.scalar(select(TrialClaim).where(TrialClaim.tenant_id==tenant_id,TrialClaim.telegram_user_id==telegram_user_id))
            if old: raise ValueError("سرویس آزمایشی قبلاً برای این حساب فعال شده است.")
            plan=await db.scalar(select(Plan).where(Plan.tenant_id==tenant_id,Plan.enabled==True).order_by(Plan.id.asc()))
            if plan is None: raise LookupError("در حال حاضر پلن آزمایشی در دسترس نیست.")
            db.add(TrialClaim(tenant_id=tenant_id,telegram_user_id=telegram_user_id,plan_id=plan.id))
            await db.commit(); return plan
SERVICE=TrialService()

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.db.models import Discount
from app.db.session import AsyncSessionLocal
from app.runtime.context import require_tenant


class DiscountService:
    async def list(self):
        tenant_id = require_tenant()
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Discount).where(Discount.tenant_id == tenant_id).order_by(Discount.created_at.desc()))
            return list(result.scalars().all())

    async def get(self, discount_id: int):
        tenant_id = require_tenant()
        async with AsyncSessionLocal() as db:
            return await db.scalar(select(Discount).where(Discount.tenant_id == tenant_id, Discount.id == discount_id))

    async def create(self, code: str, percent: float, max_uses: int | None = None, expires_at: datetime | None = None):
        tenant_id = require_tenant()
        code = code.strip().upper()
        if not code or len(code) > 64:
            raise ValueError("کد تخفیف نامعتبر است.")
        if not 0 < percent <= 100:
            raise ValueError("درصد تخفیف باید بین 1 تا 100 باشد.")
        if max_uses is not None and max_uses <= 0:
            raise ValueError("سقف استفاده باید بزرگ‌تر از صفر باشد.")
        async with AsyncSessionLocal() as db:
            existing = await db.scalar(select(Discount).where(Discount.tenant_id == tenant_id, Discount.code == code))
            if existing:
                raise ValueError("این کد تخفیف قبلاً ثبت شده است.")
            item = Discount(tenant_id=tenant_id, code=code, percent=percent, max_uses=max_uses, enabled=True, expires_at=expires_at)
            db.add(item)
            await db.commit()
            await db.refresh(item)
            return item

    async def toggle(self, discount_id: int):
        item = await self.get(discount_id)
        if not item:
            raise LookupError("کد تخفیف پیدا نشد.")
        async with AsyncSessionLocal() as db:
            item = await db.merge(item)
            item.enabled = not item.enabled
            await db.commit()
            await db.refresh(item)
            return item

    async def delete(self, discount_id: int):
        item = await self.get(discount_id)
        if not item:
            raise LookupError("کد تخفیف پیدا نشد.")
        async with AsyncSessionLocal() as db:
            item = await db.merge(item)
            await db.delete(item)
            await db.commit()


SERVICE = DiscountService()

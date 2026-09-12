from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select

from app.db.models import Discount
from app.db.session import AsyncSessionLocal
from app.runtime.context import require_tenant


class DiscountService:
    async def list(self):
        tenant_id = require_tenant()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Discount)
                .where(Discount.tenant_id == tenant_id)
                .order_by(Discount.created_at.desc())
            )
            return list(result.scalars().all())

    async def get(self, discount_id: int):
        tenant_id = require_tenant()
        async with AsyncSessionLocal() as db:
            return await db.scalar(
                select(Discount).where(
                    Discount.tenant_id == tenant_id,
                    Discount.id == discount_id,
                )
            )

    async def get_by_code(self, code: str):
        tenant_id = require_tenant()
        code = code.strip().upper()
        if not code:
            return None
        async with AsyncSessionLocal() as db:
            return await db.scalar(
                select(Discount).where(
                    Discount.tenant_id == tenant_id,
                    Discount.code == code,
                )
            )

    @staticmethod
    def _check(item: Discount) -> None:
        if not item.enabled:
            raise ValueError("این کد تخفیف غیرفعال است.")
        if item.expires_at and item.expires_at <= datetime.now(timezone.utc):
            raise ValueError("اعتبار این کد تخفیف به پایان رسیده است.")
        if item.max_uses is not None and item.used_count >= item.max_uses:
            raise ValueError("ظرفیت استفاده از این کد تکمیل شده است.")

    async def validate(self, code: str):
        item = await self.get_by_code(code)
        if item is None:
            raise LookupError("کد تخفیف پیدا نشد.")
        self._check(item)
        return item

    async def calculate(self, code: str, amount: float):
        if amount < 0:
            raise ValueError("مبلغ نامعتبر است.")
        item = await self.validate(code)
        discount = round(amount * float(item.percent) / 100)
        return item, discount, max(0.0, round(amount - discount))

    async def redeem(self, discount_id: int):
        """Atomically reserve one usage for a checkout.

        The row is locked before the usage counter is incremented so two
        concurrent checkouts cannot both consume the final available slot.
        """
        tenant_id = require_tenant()
        async with AsyncSessionLocal() as db:
            item = await db.scalar(
                select(Discount)
                .where(Discount.tenant_id == tenant_id, Discount.id == discount_id)
                .with_for_update()
            )
            if item is None:
                raise LookupError("کد تخفیف پیدا نشد.")
            self._check(item)
            item.used_count += 1
            await db.commit()
            await db.refresh(item)
            return item

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
            existing = await db.scalar(
                select(Discount).where(
                    Discount.tenant_id == tenant_id,
                    Discount.code == code,
                )
            )
            if existing:
                raise ValueError("این کد تخفیف قبلاً ثبت شده است.")
            item = Discount(
                tenant_id=tenant_id,
                code=code,
                percent=percent,
                max_uses=max_uses,
                enabled=True,
                expires_at=expires_at,
            )
            db.add(item)
            await db.commit()
            await db.refresh(item)
            return item

    async def toggle(self, discount_id: int):
        tenant_id = require_tenant()
        async with AsyncSessionLocal() as db:
            item = await db.scalar(
                select(Discount).where(
                    Discount.tenant_id == tenant_id,
                    Discount.id == discount_id,
                )
            )
            if not item:
                raise LookupError("کد تخفیف پیدا نشد.")
            item.enabled = not item.enabled
            await db.commit()
            await db.refresh(item)
            return item

    async def delete(self, discount_id: int):
        tenant_id = require_tenant()
        async with AsyncSessionLocal() as db:
            item = await db.scalar(
                select(Discount).where(
                    Discount.tenant_id == tenant_id,
                    Discount.id == discount_id,
                )
            )
            if not item:
                raise LookupError("کد تخفیف پیدا نشد.")
            if item.used_count > 0:
                raise ValueError("کد تخفیف سابقه استفاده دارد و قابل حذف نیست؛ آن را غیرفعال کنید.")
            await db.delete(item)
            await db.commit()


SERVICE = DiscountService()

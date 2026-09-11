from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.db.models import RepresentativeSetting
from app.db.session import SessionFactory
from app.runtime.context import require_tenant

DEFAULTS = {
    "brand": "",
    "support_username": "",
    "timezone": "Asia/Tehran",
    "payment_card_number": "",
    "payment_card_holder": "",
}


class RepresentativeSettingsService:
    async def snapshot(self) -> dict[str, str]:
        tenant = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            rows = (await session.execute(
                select(RepresentativeSetting).where(RepresentativeSetting.tenant_id == tenant)
            )).scalars().all()
        values = dict(DEFAULTS)
        for row in rows:
            if row.key in DEFAULTS:
                values[row.key] = row.value
        return values

    async def set(self, key: str, value: str) -> dict[str, str]:
        if key not in DEFAULTS:
            raise ValueError("تنظیم نامعتبر است.")
        value = value.strip()
        if not value:
            raise ValueError("مقدار نمی‌تواند خالی باشد.")
        if key == "brand":
            if len(value) > 120:
                raise ValueError("نام برند بیش از حد طولانی است.")
        elif key == "support_username":
            value = value.lstrip("@").strip()
            if not value or len(value) > 64 or not value.replace("_", "").isalnum():
                raise ValueError("یوزرنیم پشتیبانی نامعتبر است.")
        elif key == "timezone":
            if len(value) > 80:
                raise ValueError("منطقه زمانی نامعتبر است.")
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("منطقه زمانی معتبر نیست؛ مثال: Asia/Tehran") from exc
        elif key == "payment_card_number":
            digits = value.replace("-", "").replace(" ", "")
            if not digits.isdigit() or len(digits) != 16:
                raise ValueError("شماره کارت باید ۱۶ رقم باشد.")
            value = digits
        elif key == "payment_card_holder":
            if len(value) > 120:
                raise ValueError("نام صاحب کارت بیش از حد طولانی است.")

        tenant = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            row = await session.scalar(select(RepresentativeSetting).where(
                RepresentativeSetting.tenant_id == tenant,
                RepresentativeSetting.key == key,
            ))
            if row is None:
                session.add(RepresentativeSetting(tenant_id=tenant, key=key, value=value))
            else:
                row.value = value
            await session.commit()
        return await self.snapshot()


SERVICE = RepresentativeSettingsService()

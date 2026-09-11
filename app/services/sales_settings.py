from __future__ import annotations

from sqlalchemy import select
from app.db.models import SalesSetting
from app.db.session import session_scope
from app.runtime.context import require_tenant

_DEFAULTS = {"sales_enabled": True, "require_payment_confirmation": True, "allow_pending_orders": True, "currency": "تومان", "support_username": ""}

class SalesSettingsService:
    async def snapshot(self) -> dict[str, object]:
        tenant = require_tenant()
        async for session in session_scope():
            rows = (await session.execute(select(SalesSetting).where(SalesSetting.tenant_id == tenant))).scalars().all()
        values = dict(_DEFAULTS)
        for row in rows:
            raw = row.value
            if row.key in {"sales_enabled", "require_payment_confirmation", "allow_pending_orders"}:
                values[row.key] = raw == "1"
            else:
                values[row.key] = raw
        return values

    async def set(self, key: str, value: object) -> dict[str, object]:
        if key not in _DEFAULTS:
            raise ValueError("تنظیم فروش نامعتبر است.")
        tenant = require_tenant()
        encoded = ("1" if bool(value) else "0") if isinstance(_DEFAULTS[key], bool) else str(value).strip()
        if key == "currency" and not encoded:
            raise ValueError("واحد قیمت نمی‌تواند خالی باشد.")
        if key == "support_username":
            encoded = encoded.lstrip("@").strip()
        async for session in session_scope():
            row = (await session.execute(select(SalesSetting).where(SalesSetting.tenant_id == tenant, SalesSetting.key == key))).scalar_one_or_none()
            if row is None:
                session.add(SalesSetting(tenant_id=tenant, key=key, value=encoded))
            else:
                row.value = encoded
            await session.commit()
        return await self.snapshot()

SERVICE = SalesSettingsService()

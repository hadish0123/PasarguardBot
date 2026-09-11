from __future__ import annotations

from app.runtime.context import require_tenant


_DEFAULTS = {
    "sales_enabled": True,
    "require_payment_confirmation": True,
    "allow_pending_orders": True,
    "currency": "تومان",
    "support_username": "",
}


class SalesSettingsService:
    _values: dict[str, dict[str, object]] = {}

    def _tenant(self):
        return require_tenant()

    async def snapshot(self) -> dict[str, object]:
        tenant = self._tenant()
        values = dict(_DEFAULTS)
        values.update(self._values.get(tenant, {}))
        return values

    async def set(self, key: str, value: object) -> dict[str, object]:
        if key not in _DEFAULTS:
            raise ValueError("تنظیم فروش نامعتبر است.")
        tenant = self._tenant()
        self._values.setdefault(tenant, {})[key] = value
        return await self.snapshot()


SERVICE = SalesSettingsService()

from __future__ import annotations

import asyncio
import re

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError

from app.db.models import Order, Plan, TenantRecord, TrialClaim
from app.db.session import AsyncSessionLocal, SessionFactory
from app.runtime.context import require_tenant
from app.services.representative_settings import SERVICE as SETTINGS


_LOCKS: dict[tuple[str, int], asyncio.Lock] = {}
_TENANT_ALLOC_LOCKS: dict[str, asyncio.Lock] = {}
_TEST_CONFIG_RE = re.compile(r"^test([1-9][0-9]{0,3})$")


def _lock(key):
    return _LOCKS.setdefault(key, asyncio.Lock())


def _tenant_alloc_lock(tenant_id: str):
    return _TENANT_ALLOC_LOCKS.setdefault(str(tenant_id), asyncio.Lock())


async def _allocate_test_config_name(db, tenant_id: str) -> str:
    """Reserve the first unused testN name for this representative tenant."""
    tenant = await db.scalar(
        select(TenantRecord)
        .where(TenantRecord.id == tenant_id)
        .with_for_update()
    )
    if tenant is None:
        raise LookupError("نمایندگی پیدا نشد.")

    result = await db.execute(
        text(
            "SELECT config_name FROM representative_orders "
            "WHERE tenant_id=:tenant_id AND config_name LIKE 'test%'"
        ),
        {"tenant_id": tenant_id},
    )
    used: set[int] = set()
    for (value,) in result.all():
        match = _TEST_CONFIG_RE.fullmatch(str(value or "").strip())
        if match:
            used.add(int(match.group(1)))

    for index in range(1, 1001):
        if index not in used:
            return f"test{index}"
    raise ValueError("ظرفیت نام کانفیگ سرویس تستی تکمیل شده است (test1 تا test1000).")


class TrialService:
    async def snapshot(self) -> dict[str, str]:
        return await SETTINGS.snapshot()

    async def claim(self, telegram_user_id: int):
        tenant_id = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        key = (tenant_id, int(telegram_user_id))
        async with _lock(key):
            settings = await SETTINGS.snapshot()
            if settings.get("trial_enabled", "1") != "1":
                raise ValueError("سرویس آزمایشی در حال حاضر غیرفعال است.")
            try:
                value = float(settings.get("trial_volume_value", "1"))
            except ValueError:
                raise ValueError("حجم سرویس تستی تنظیم نشده است.")
            unit = settings.get("trial_volume_unit", "GB").upper()
            try:
                days = int(settings.get("trial_days", "1"))
            except ValueError:
                raise ValueError("مدت سرویس تستی تنظیم نشده است.")
            volume_gb = value / 1024 if unit == "MB" else value
            if volume_gb <= 0 or days <= 0:
                raise ValueError("تنظیمات سرویس تستی نامعتبر است.")

            # Config names are allocated per representative tenant. The tenant
            # row is locked so concurrent trial claims cannot receive the same
            # testN name, even when they come from different users.
            async with _tenant_alloc_lock(tenant_id):
                async with AsyncSessionLocal() as db:
                    old = await db.scalar(
                        select(TrialClaim).where(
                            TrialClaim.tenant_id == tenant_id,
                            TrialClaim.telegram_user_id == telegram_user_id,
                        )
                    )
                    if old:
                        raise ValueError("سرویس آزمایشی قبلاً برای این حساب فعال شده است.")

                    plan = await db.scalar(
                        select(Plan)
                        .where(Plan.tenant_id == tenant_id, Plan.enabled.is_(True))
                        .order_by(Plan.id.asc())
                    )
                    if plan is None:
                        raise LookupError("حداقل یک پلن فعال برای ساخت سرویس تستی لازم است.")

                    config_name = await _allocate_test_config_name(db, tenant_id)
                    plan_name = f"سرویس تستی | {value:g} {unit} | {days} روز"
                    order = Order(
                        tenant_id=tenant_id,
                        telegram_user_id=telegram_user_id,
                        plan_id=plan.id,
                        plan_name=plan_name,
                        volume_gb=volume_gb,
                        days=days,
                        amount=0,
                        status="paid",
                    )
                    db.add(order)
                    await db.flush()
                    await db.execute(
                        text(
                            "UPDATE representative_orders "
                            "SET config_name=:config_name WHERE id=:order_id"
                        ),
                        {"config_name": config_name, "order_id": order.id},
                    )
                    db.add(
                        TrialClaim(
                            tenant_id=tenant_id,
                            telegram_user_id=telegram_user_id,
                            plan_id=plan.id,
                        )
                    )
                    try:
                        await db.commit()
                    except IntegrityError as exc:
                        await db.rollback()
                        raise ValueError("سرویس آزمایشی قبلاً برای این حساب فعال شده است.") from exc
                    order_id = order.id

            try:
                from app.services.pasarguard_provisioning import PasarguardProvisioningService

                subscription = await PasarguardProvisioningService().provision_paid_order(order_id)
                return plan, subscription, config_name
            except Exception:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        delete(TrialClaim).where(
                            TrialClaim.tenant_id == tenant_id,
                            TrialClaim.telegram_user_id == telegram_user_id,
                        )
                    )
                    await db.execute(
                        delete(Order).where(
                            Order.tenant_id == tenant_id,
                            Order.id == order_id,
                        )
                    )
                    await db.commit()
                raise

    async def reset_all(self) -> int:
        tenant_id = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with AsyncSessionLocal() as db:
            result = await db.execute(delete(TrialClaim).where(TrialClaim.tenant_id == tenant_id))
            await db.commit()
            return int(result.rowcount or 0)

    async def claim_count(self) -> int:
        tenant_id = require_tenant()
        async with AsyncSessionLocal() as db:
            return int(
                await db.scalar(
                    select(func.count(TrialClaim.id)).where(TrialClaim.tenant_id == tenant_id)
                )
                or 0
            )


SERVICE = TrialService()

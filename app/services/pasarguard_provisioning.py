from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Order, Plan, ServiceSubscription, TenantRecord
from app.db.session import SessionFactory
from app.runtime.context import require_tenant
from app.services.pasarguard import PasarguardClient
from app.services.secrets import get_secret_box


PROVISIONING_STALE_AFTER = timedelta(minutes=10)


class PasarguardProvisioningService:
    async def provision_paid_order(self, order_id: int) -> ServiceSubscription:
        tenant_id = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")

        async with SessionFactory() as session:
            order = await session.scalar(
                select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
            )
            if order is None:
                raise LookupError("سفارش پیدا نشد.")
            if order.status != "paid":
                raise ValueError("فقط سفارش پرداخت‌شده قابل تحویل است.")

            subscription = await session.scalar(
                select(ServiceSubscription)
                .where(
                    ServiceSubscription.order_id == order.id,
                    ServiceSubscription.tenant_id == tenant_id,
                )
                .with_for_update()
            )
            if subscription is None:
                subscription = ServiceSubscription(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    telegram_user_id=order.telegram_user_id,
                    plan_id=order.plan_id,
                    plan_name=order.plan_name,
                    volume_gb=order.volume_gb,
                    days=order.days,
                    status="pending_provisioning",
                    provider="pasarguard",
                )
                session.add(subscription)
                await session.flush()

            if subscription.status == "active":
                return subscription

            now = datetime.now(timezone.utc)
            if subscription.status == "provisioning":
                updated = subscription.updated_at
                if updated and updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if updated and now - updated < PROVISIONING_STALE_AFTER:
                    raise ValueError("تحویل این سفارش در حال انجام است؛ چند دقیقه بعد دوباره تلاش کنید.")

            plan = await session.scalar(
                select(Plan).where(Plan.id == order.plan_id, Plan.tenant_id == tenant_id)
            )
            tenant = await session.get(TenantRecord, tenant_id)
            if plan is None or tenant is None:
                raise LookupError("پلن یا نمایندگی پیدا نشد.")

            subscription.status = "provisioning"
            await session.commit()
            await session.refresh(subscription)

            box = get_secret_box()
            api_key = box.decrypt(tenant.panel_api_key_encrypted)
            client = PasarguardClient(tenant.panel_url, api_key)
            username = f"tg_{order.telegram_user_id}_{order.id}"
            note = (
                f"Representative tenant={tenant_id}; order={order.id}; "
                f"telegram_user={order.telegram_user_id}; plan={plan.name}"
            )

            try:
                provisioned = await client.create_user_for_plan(
                    username=username,
                    volume_gb=order.volume_gb,
                    days=order.days,
                    note=note,
                )
            except Exception:
                subscription.status = "pending_provisioning"
                await session.commit()
                raise

            now = datetime.now(timezone.utc)
            subscription.provider_service_id = provisioned.service_id
            subscription.subscription_url = provisioned.subscription_url
            subscription.starts_at = now
            subscription.expires_at = now + timedelta(days=order.days)
            subscription.status = "active"
            await session.commit()
            await session.refresh(subscription)
            return subscription

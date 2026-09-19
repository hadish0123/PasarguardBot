from __future__ import annotations

from sqlalchemy import case, func, select

from app.core.exceptions import PermissionDenied
from app.core.config import settings
from app.db.models import Order, RegistrationStatus, RepresentativeRegistration, RepresentativeUser, ServiceSubscription, TenantRecord, TenantStatus
from app.db.session import SessionFactory
from app.services.secrets import get_secret_box


class CentralAdminService:
    """Central-only authorization and registration/tenant management boundary."""

    @staticmethod
    def is_admin(user_id: int) -> bool:
        return user_id in settings.admin_ids

    @classmethod
    def require_admin(cls, user_id: int) -> None:
        if not cls.is_admin(user_id):
            raise PermissionDenied("central admin permission required")

    async def pending(self) -> list[RepresentativeRegistration]:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(
                select(RepresentativeRegistration)
                .where(RepresentativeRegistration.status == RegistrationStatus.PENDING.value)
                .order_by(RepresentativeRegistration.id.asc())
            )
            return list(result.scalars().all())

    async def get(self, registration_id: int) -> RepresentativeRegistration | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.get(RepresentativeRegistration, registration_id)

    async def approve(self, registration_id: int) -> RepresentativeRegistration:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(RepresentativeRegistration, registration_id)
            if record is None:
                raise LookupError("registration not found")
            if record.status != RegistrationStatus.PENDING.value:
                raise ValueError("registration is not pending")
            record.status = RegistrationStatus.PROVISIONING.value
            await session.commit()
            await session.refresh(record)
            return record

    async def reject(self, registration_id: int, reason: str) -> RepresentativeRegistration:
        reason = reason.strip()
        if len(reason) < 3:
            raise ValueError("rejection reason is required")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(RepresentativeRegistration, registration_id)
            if record is None:
                raise LookupError("registration not found")
            if record.status != RegistrationStatus.PENDING.value:
                raise ValueError("registration is not pending")
            record.status = RegistrationStatus.REJECTED.value
            record.rejection_reason = reason[:2000]
            await session.commit()
            await session.refresh(record)
            return record

    async def tenants(self) -> list[TenantRecord]:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            result = await session.execute(select(TenantRecord).order_by(TenantRecord.id.asc()))
            return list(result.scalars().all())

    async def get_tenant(self, tenant_id: str) -> TenantRecord | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(TenantRecord, tenant_id)
            if record is not None:
                return record
            if tenant_id.isdigit():
                return await session.scalar(select(TenantRecord).where(TenantRecord.bot_id == int(tenant_id)))
            return None

    async def get_tenant_by_bot_id(self, bot_id: int) -> TenantRecord | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.scalar(select(TenantRecord).where(TenantRecord.bot_id == bot_id))

    async def _get_tenant_in_session(self, session, tenant_id: str) -> TenantRecord | None:
        record = await session.get(TenantRecord, tenant_id)
        if record is not None:
            return record
        if tenant_id.isdigit():
            return await session.scalar(select(TenantRecord).where(TenantRecord.bot_id == int(tenant_id)))
        return None

    async def set_tenant_status(self, tenant_id: str, status: TenantStatus) -> TenantRecord:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await self._get_tenant_in_session(session, tenant_id)
            if record is None:
                raise LookupError("tenant not found")
            record.status = status.value
            await session.commit()
            await session.refresh(record)
            return record

    async def change_tenant_owner(self, tenant_id: str, owner_id: int) -> TenantRecord:
        if owner_id <= 0:
            raise ValueError("invalid owner id")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await self._get_tenant_in_session(session, tenant_id)
            if record is None:
                raise LookupError("tenant not found")
            record.owner_id = owner_id
            registration = await session.scalar(
                select(RepresentativeRegistration).where(RepresentativeRegistration.id == record.registration_id)
            )
            if registration is not None:
                registration.owner_id = owner_id
            await session.commit()
            await session.refresh(record)
            return record

    async def delete_tenant(self, tenant_id: str) -> TenantRecord:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await self._get_tenant_in_session(session, tenant_id)
            if record is None:
                raise LookupError("tenant not found")
            await session.delete(record)
            await session.commit()
            return record


    async def representative_dashboard(self, query: str | None = None) -> list[dict]:
        """Return aggregated business statistics for central admin."""
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            tenants = list((await session.execute(
                select(TenantRecord).order_by(TenantRecord.created_at.desc(), TenantRecord.id.asc())
            )).scalars().all())
            order_rows = (await session.execute(
                select(
                    Order.tenant_id,
                    func.count(Order.id),
                    func.sum(case((Order.status.in_(("paid", "fulfilled")), 1), else_=0)),
                    func.coalesce(func.sum(case(
                        (Order.status.in_(("paid", "fulfilled")), Order.amount),
                        else_=0.0,
                    )), 0.0),
                ).group_by(Order.tenant_id)
            )).all()
            order_stats = {
                row[0]: {"orders": int(row[1] or 0), "paid_orders": int(row[2] or 0), "revenue": float(row[3] or 0)}
                for row in order_rows
            }
            user_rows = (await session.execute(
                select(RepresentativeUser.tenant_id, func.count(RepresentativeUser.id))
                .group_by(RepresentativeUser.tenant_id)
            )).all()
            user_stats = {row[0]: int(row[1] or 0) for row in user_rows}
            service_rows = (await session.execute(
                select(
                    ServiceSubscription.tenant_id,
                    func.count(ServiceSubscription.id),
                    func.sum(case((ServiceSubscription.status == "active", 1), else_=0)),
                ).group_by(ServiceSubscription.tenant_id)
            )).all()
            service_stats = {
                row[0]: {"services": int(row[1] or 0), "active_services": int(row[2] or 0)}
                for row in service_rows
            }
        q = (query or "").strip().lstrip("@").lower()
        result = []
        for tenant in tenants:
            orders = order_stats.get(tenant.id, {})
            services = service_stats.get(tenant.id, {})
            users = user_stats.get(tenant.id, 0)
            paid_orders = orders.get("paid_orders", 0)
            revenue = orders.get("revenue", 0.0)
            total_services = services.get("services", 0)
            active_services = services.get("active_services", 0)
            if paid_orders == 0 and revenue <= 0 and users == 0 and total_services == 0:
                rank, rank_label = "black", "⚫ بدون فروش و استفاده"
            elif paid_orders <= 2 and revenue <= 500_000:
                rank, rank_label = "red", "🔴 فعالیت کم"
            else:
                rank, rank_label = "green", "🟢 عالی"
            haystack = " ".join([tenant.brand or "", tenant.bot_username or "", str(tenant.bot_id), str(tenant.owner_id)]).lower()
            if q and q not in haystack:
                continue
            result.append({
                "tenant": tenant,
                "rank": rank,
                "rank_label": rank_label,
                "orders": orders.get("orders", 0),
                "paid_orders": paid_orders,
                "revenue": round(revenue),
                "users": users,
                "services": total_services,
                "active_services": active_services,
            })
        rank_order = {"green": 0, "red": 1, "black": 2}
        result.sort(key=lambda x: (rank_order[x["rank"]], -x["revenue"], -x["paid_orders"], -x["users"], (x["tenant"].brand or "").lower()))
        return result

    async def get_tenant_bot_token(self, tenant_id: str) -> str:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await self._get_tenant_in_session(session, tenant_id)
            if record is None or not record.bot_token_encrypted:
                raise LookupError("bot token not found")
            encrypted = record.bot_token_encrypted
        return get_secret_box().decrypt(encrypted).strip()

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.db.models import TenantRecord
from app.db.session import SessionFactory
from app.runtime.context import require_tenant
from app.services.pasarguard import PasarguardClient
from app.services.secrets import get_secret_box


@dataclass(slots=True)
class PanelStatus:
    configured: bool
    tenant_status: str
    panel_url: str | None
    panel_username: str | None
    state: str
    message: str


class PanelStatusService:
    async def snapshot(self) -> PanelStatus:
        tenant_id = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(TenantRecord, tenant_id)
            if record is None:
                raise LookupError("tenant not found")
            configured = bool(record.panel_url and record.panel_api_key_encrypted)
            if not configured:
                return PanelStatus(False, record.status, record.panel_url, record.panel_username, "missing", "اطلاعات اتصال پنل کامل نیست.")
            return PanelStatus(True, record.status, record.panel_url, record.panel_username, "unknown", "برای دریافت وضعیت، اتصال را تست کنید.")

    async def check(self) -> PanelStatus:
        tenant_id = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            record = await session.get(TenantRecord, tenant_id)
            if record is None:
                raise LookupError("tenant not found")
            if not record.panel_url or not record.panel_api_key_encrypted:
                return PanelStatus(False, record.status, record.panel_url, record.panel_username, "missing", "اطلاعات اتصال پنل کامل نیست.")
            try:
                api_key = get_secret_box().decrypt(record.panel_api_key_encrypted)
                await PasarguardClient(record.panel_url, api_key).health()
                return PanelStatus(True, record.status, record.panel_url, record.panel_username, "connected", "اتصال به پنل پاسارگارد با موفقیت برقرار است.")
            except PermissionError:
                return PanelStatus(True, record.status, record.panel_url, record.panel_username, "unauthorized", "احراز هویت پنل ناموفق است؛ کلید API را بررسی کنید.")
            except Exception as exc:
                message = str(exc).strip() or "خطای نامشخص در اتصال پنل."
                return PanelStatus(True, record.status, record.panel_url, record.panel_username, "unreachable", message[:300])


SERVICE = PanelStatusService()

from __future__ import annotations

from dataclasses import dataclass

from app.db.models import RepresentativeRegistration, TenantRecord
from app.db.session import SessionFactory
from app.runtime.context import require_tenant
from app.services.logs import SERVICE as LOG_SERVICE
from app.services.pasarguard import PasarguardClient
from app.services.registration import RegistrationService
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

    @staticmethod
    def _validate_username(value: str) -> str:
        value = (value or "").strip()
        if not 2 <= len(value) <= 190 or any(ch.isspace() for ch in value):
            raise ValueError("نام کاربری پنل معتبر نیست.")
        return value

    @staticmethod
    def _validate_api_key(value: str) -> str:
        value = (value or "").strip()
        if len(value) < 8:
            raise ValueError("API Key خیلی کوتاه است.")
        if len(value) > 1000:
            raise ValueError("API Key بیش از حد طولانی است.")
        return value

    @staticmethod
    def _validate_panel_url(value: str) -> str:
        try:
            return RegistrationService.normalize_panel_url(value)
        except Exception as exc:
            raise ValueError(str(exc) or "آدرس پنل معتبر نیست.") from exc

    async def update_field(self, field: str, value: str, actor_id: int | None = None) -> PanelStatus:
        tenant_id = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")

        if field == "panel_url":
            normalized = self._validate_panel_url(value)
        elif field == "panel_username":
            normalized = self._validate_username(value)
        elif field == "panel_api_key":
            normalized = self._validate_api_key(value)
        else:
            raise ValueError("فیلد اتصال نامعتبر است.")

        async with SessionFactory() as session:
            record = await session.get(TenantRecord, tenant_id)
            if record is None:
                raise LookupError("tenant not found")

            registration = None
            if record.registration_id:
                registration = await session.get(RepresentativeRegistration, record.registration_id)

            if field == "panel_url":
                record.panel_url = normalized
                if registration is not None:
                    registration.panel_url = normalized
                log_detail = "panel_url updated"
            elif field == "panel_username":
                record.panel_username = normalized
                if registration is not None:
                    registration.panel_username = normalized
                log_detail = "panel_username updated"
            else:
                encrypted = get_secret_box().encrypt(normalized)
                record.panel_api_key_encrypted = encrypted
                if registration is not None:
                    registration.panel_api_key_encrypted = encrypted
                log_detail = "panel_api_key updated"

            await session.commit()

        try:
            await LOG_SERVICE.add("panel_connection_updated", log_detail, actor_id=actor_id)
        except Exception:
            pass

        return await self.check()


SERVICE = PanelStatusService()

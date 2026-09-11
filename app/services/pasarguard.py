from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.exceptions import ExternalServiceError


@dataclass(frozen=True)
class ProvisionedUser:
    service_id: str
    subscription_url: str | None


class PasarguardClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/api/system/info",
                    headers=self._headers(),
                )
            if response.status_code in (401, 403):
                raise PermissionError("احراز هویت پنل ناموفق است؛ کلید API را بررسی کنید.")
            if not response.is_success:
                raise ExternalServiceError(
                    f"پنل پاسارگارد پاسخ HTTP {response.status_code} برگرداند."
                )
            return True
        except PermissionError:
            raise
        except httpx.HTTPError as exc:
            raise ExternalServiceError("ارتباط با پنل پاسارگارد برقرار نشد.") from exc

    async def create_user_from_template(
        self,
        user_template_id: int,
        username: str,
        note: str | None = None,
    ) -> ProvisionedUser:
        if user_template_id <= 0:
            raise ValueError("شناسه Template پاسارگارد نامعتبر است.")
        if not username or len(username) < 3:
            raise ValueError("نام کاربری پاسارگارد نامعتبر است.")

        payload = {
            "user_template_id": int(user_template_id),
            "username": username,
        }
        if note:
            payload["note"] = note

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{self.base_url}/api/user/from_template",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ExternalServiceError("ارتباط با پنل پاسارگارد برای ساخت سرویس برقرار نشد.") from exc

        if response.status_code in (401, 403):
            raise PermissionError("کلید API پاسارگارد اجازه ساخت کاربر را ندارد.")
        if not response.is_success:
            detail = response.text.strip()
            if len(detail) > 300:
                detail = detail[:300]
            raise ExternalServiceError(
                f"ساخت کاربر در پاسارگارد ناموفق بود (HTTP {response.status_code}). {detail}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError("پاسخ ساخت کاربر پاسارگارد JSON معتبر نیست.") from exc

        # PasarGuard returns a user object. Keep parsing tolerant across minor
        # API response shape changes while refusing to mark a service active
        # without a real provider identifier.
        if not isinstance(data, dict):
            raise ExternalServiceError("پاسخ پاسارگارد برای کاربر ساختاری نامعتبر دارد.")

        service_id = data.get("id") or data.get("user_id") or data.get("username")
        subscription_url = (
            data.get("subscription_url")
            or data.get("subscriptionUrl")
            or data.get("sub_url")
            or data.get("subscription")
        )
        if isinstance(subscription_url, dict):
            subscription_url = (
                subscription_url.get("url")
                or subscription_url.get("subscription_url")
            )

        if service_id is None:
            raise ExternalServiceError(
                "پاسخ پاسارگارد شناسه سرویس ایجادشده را برنگرداند؛ سرویس فعال اعلام نشد."
            )

        return ProvisionedUser(
            service_id=str(service_id),
            subscription_url=str(subscription_url) if subscription_url else None,
        )

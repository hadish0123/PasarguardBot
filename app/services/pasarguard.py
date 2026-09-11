from __future__ import annotations

from dataclasses import dataclass
import time
import uuid

import httpx

from app.core.exceptions import ExternalServiceError


@dataclass(frozen=True)
class ProvisionedUser:
    service_id: str
    subscription_url: str | None


@dataclass(frozen=True)
class PanelProbe:
    client_count: int
    test_user: ProvisionedUser


class PasarguardClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()

    def _headers(self) -> dict[str, str]:
        return {
            "X-Api-Key": self.api_key,
            "Authorization": f"ApiKey {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.request(method, f"{self.base_url}{path}", headers=self._headers(), **kwargs)
        except httpx.HTTPError as exc:
            raise ExternalServiceError("ارتباط با پنل پاسارگارد برقرار نشد؛ آدرس پنل یا دسترسی شبکه را بررسی کنید.") from exc
        if response.status_code in (401, 403):
            raise PermissionError("کلید API پاسارگارد معتبر نیست یا دسترسی لازم را ندارد.")
        return response

    async def health(self) -> bool:
        response = await self._request("GET", "/api/system/resources")
        if not response.is_success:
            raise ExternalServiceError(f"پنل پاسارگارد پاسخ HTTP {response.status_code} برگرداند.")
        return True

    async def client_count(self) -> int:
        response = await self._request("GET", "/api/users", params={"limit": 1})
        if not response.is_success:
            raise ExternalServiceError(f"دریافت تعداد کلاینت‌ها ناموفق بود (HTTP {response.status_code}).")
        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError("پاسخ تعداد کلاینت‌های پاسارگارد JSON معتبر نیست.") from exc
        if isinstance(data, dict) and isinstance(data.get("total"), int):
            return data["total"]
        if isinstance(data, list):
            return len(data)
        raise ExternalServiceError("ساختار پاسخ تعداد کلاینت‌های پاسارگارد نامعتبر است.")

    async def _first_user_template_id(self) -> int:
        response = await self._request("GET", "/api/user_templates")
        if not response.is_success:
            raise ExternalServiceError(f"دریافت User Templateهای پاسارگارد ناموفق بود (HTTP {response.status_code}).")
        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError("پاسخ User Template پاسارگارد JSON معتبر نیست.") from exc
        items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
        if not items:
            raise ExternalServiceError("در پنل پاسارگارد هیچ User Template فعالی برای ساخت کلاینت تست وجود ندارد.")
        template_id = items[0].get("id") if isinstance(items[0], dict) else None
        if not isinstance(template_id, int) or template_id <= 0:
            raise ExternalServiceError("شناسه User Template پاسارگارد معتبر نیست.")
        return template_id

    async def create_test_user(self) -> ProvisionedUser:
        template_id = await self._first_user_template_id()
        username = f"pasarguard_test_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        response = await self._request(
            "POST", "/api/user/from_template",
            json={"user_template_id": template_id, "username": username},
        )
        if not response.is_success:
            detail = response.text.strip()[:300]
            raise ExternalServiceError(f"ساخت کلاینت تستی پاسارگارد ناموفق بود (HTTP {response.status_code}). {detail}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError("پاسخ ساخت کلاینت تستی JSON معتبر نیست.") from exc
        if not isinstance(data, dict):
            raise ExternalServiceError("پاسخ ساخت کلاینت تستی پاسارگارد نامعتبر است.")
        service_id = data.get("id") or data.get("user_id") or data.get("username")
        subscription_url = data.get("subscription_url") or data.get("subscriptionUrl")
        if service_id is None:
            raise ExternalServiceError("پاسارگارد کلاینت تستی را ساخت اما شناسه آن را برنگرداند.")
        return ProvisionedUser(str(service_id), str(subscription_url) if subscription_url else None)

    async def probe(self) -> PanelProbe:
        await self.health()
        count = await self.client_count()
        test_user = await self.create_test_user()
        return PanelProbe(client_count=count + 1, test_user=test_user)

    async def create_user_from_template(self, user_template_id: int, username: str, note: str | None = None) -> ProvisionedUser:
        if user_template_id <= 0 or not username or len(username) < 3:
            raise ValueError("اطلاعات ساخت کاربر پاسارگارد نامعتبر است.")
        payload = {"user_template_id": int(user_template_id), "username": username}
        if note:
            payload["note"] = note
        response = await self._request("POST", "/api/user/from_template", json=payload)
        if not response.is_success:
            raise ExternalServiceError(f"ساخت کاربر در پاسارگارد ناموفق بود (HTTP {response.status_code}). {response.text.strip()[:300]}")
        data = response.json()
        if not isinstance(data, dict):
            raise ExternalServiceError("پاسخ پاسارگارد برای کاربر ساختاری نامعتبر دارد.")
        service_id = data.get("id") or data.get("user_id") or data.get("username")
        subscription_url = data.get("subscription_url") or data.get("subscriptionUrl")
        if service_id is None:
            raise ExternalServiceError("پاسخ پاسارگارد شناسه سرویس ایجادشده را برنگرداند.")
        return ProvisionedUser(str(service_id), str(subscription_url) if subscription_url else None)

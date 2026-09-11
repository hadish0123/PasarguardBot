from __future__ import annotations

from dataclasses import dataclass
import time
import uuid
from urllib.parse import urljoin, urlsplit, urlunsplit

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
        self.base_url = self._normalize_base_url(base_url)
        self.api_key = api_key.strip()

    @staticmethod
    def _normalize_base_url(value: str) -> str:
        value = value.strip().rstrip("/")
        if not value:
            return value
        parsed = urlsplit(value)
        if parsed.scheme and parsed.netloc:
            path = parsed.path.rstrip("/")
            for suffix in ("/dashboard/login", "/dashboard", "/login"):
                if path.endswith(suffix):
                    path = path[: -len(suffix)].rstrip("/")
                    break
            return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")
        return value

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self.api_key, "Accept": "application/json", "Content-Type": "application/json"}

    def _absolute_subscription_url(self, value: object) -> str | None:
        if value is None:
            return None
        subscription = str(value).strip()
        if not subscription:
            return None
        return urljoin(f"{self.base_url}/", subscription)

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.request(method, f"{self.base_url}{path}", headers=self._headers(), **kwargs)
        except httpx.HTTPError as exc:
            raise ExternalServiceError("ارتباط با پنل پاسارگارد برقرار نشد؛ آدرس پنل یا دسترسی شبکه را بررسی کنید.") from exc
        if response.status_code in (401, 403):
            detail = response.text.strip()[:300]
            raise PermissionError(f"کلید API پاسارگارد معتبر نیست یا دسترسی لازم را ندارد. {detail}".strip())
        return response

    async def health(self) -> bool:
        response = await self._request("GET", "/api/admin")
        if not response.is_success:
            detail = response.text.strip()[:300]
            raise ExternalServiceError(f"اتصال به API پاسارگارد ناموفق بود (HTTP {response.status_code}). {detail}")
        return True

    async def client_count(self) -> int:
        response = await self._request("GET", "/api/users", params={"limit": 1})
        if not response.is_success:
            detail = response.text.strip()[:500]
            raise ExternalServiceError(f"دریافت تعداد کلاینت‌ها ناموفق بود (HTTP {response.status_code}). {detail}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError("پاسخ تعداد کلاینت‌های پاسارگارد JSON معتبر نیست.") from exc
        if isinstance(data, dict) and isinstance(data.get("total"), int):
            return data["total"]
        if isinstance(data, dict) and isinstance(data.get("users"), list):
            return len(data["users"])
        if isinstance(data, list):
            return len(data)
        raise ExternalServiceError("ساختار پاسخ تعداد کلاینت‌های پاسارگارد نامعتبر است.")

    async def _first_group_id(self) -> int | None:
        response = await self._request("GET", "/api/groups/simple", params={"limit": 100})
        if response.status_code == 404:
            return None
        if not response.is_success:
            detail = response.text.strip()[:500]
            raise ExternalServiceError(f"دریافت گروه‌های پاسارگارد ناموفق بود (HTTP {response.status_code}). {detail}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError("پاسخ گروه‌های پاسارگارد JSON معتبر نیست.") from exc
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("items") or data.get("groups") or []
        else:
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("is_disabled") is True or item.get("disabled") is True:
                continue
            item_id = item.get("id")
            if isinstance(item_id, int) and item_id > 0:
                return item_id
        return None

    async def create_test_user(self) -> ProvisionedUser:
        username = f"pasarguard_test_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        group_id = await self._first_group_id()
        if group_id is None:
            raise ExternalServiceError("هیچ گروه فعالی در پنل پاسارگارد پیدا نشد؛ کلاینت تستی بدون گروه ساخته نمی‌شود.")
        response = await self._request("POST", "/api/user", json={"username": username, "group_ids": [group_id]})
        if not response.is_success:
            detail = response.text.strip()[:500]
            raise ExternalServiceError(f"ساخت کلاینت تستی پاسارگارد ناموفق بود (HTTP {response.status_code}). {detail}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError("پاسخ ساخت کلاینت تستی JSON معتبر نیست.") from exc
        if not isinstance(data, dict):
            raise ExternalServiceError("پاسخ ساخت کلاینت تستی پاسارگارد نامعتبر است.")
        service_id = data.get("id") or data.get("user_id") or data.get("username")
        subscription_url = self._absolute_subscription_url(data.get("subscription_url") or data.get("subscriptionUrl"))
        if service_id is None:
            raise ExternalServiceError("پاسارگارد کلاینت تستی را ساخت اما شناسه آن را برنگرداند.")
        return ProvisionedUser(str(service_id), subscription_url)

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
        subscription_url = self._absolute_subscription_url(data.get("subscription_url") or data.get("subscriptionUrl"))
        if service_id is None:
            raise ExternalServiceError("پاسخ پاسارگارد شناسه سرویس ایجادشده را برنگرداند.")
        return ProvisionedUser(str(service_id), subscription_url)

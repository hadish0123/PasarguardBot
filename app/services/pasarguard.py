from __future__ import annotations

import httpx

from app.core.exceptions import ExternalServiceError


class PasarguardClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/api/system/info",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            if response.status_code in (401, 403):
                raise PermissionError("احراز هویت پنل ناموفق است؛ کلید API را بررسی کنید.")
            if not response.is_success:
                raise ExternalServiceError(f"پنل پاسارگارد پاسخ HTTP {response.status_code} برگرداند.")
            return True
        except PermissionError:
            raise
        except httpx.HTTPError as exc:
            raise ExternalServiceError("ارتباط با پنل پاسارگارد برقرار نشد.") from exc

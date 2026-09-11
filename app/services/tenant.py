from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Tenant:
    id: str
    owner_id: int
    brand: str
    bot_username: str | None
    panel_url: str


class TenantService:
    """Tenant lifecycle boundary. DB implementation is intentionally isolated here."""

    async def provision(self, owner_id: int, brand: str, panel_url: str, bot_username: str | None) -> Tenant:
        raise NotImplementedError

    async def suspend(self, tenant_id: str) -> None:
        raise NotImplementedError

    async def activate(self, tenant_id: str) -> None:
        raise NotImplementedError

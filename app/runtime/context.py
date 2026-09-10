from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class TenantRuntime:
    registration_id: int
    owner_user_id: int
    bot_id: int
    bot_username: str | None
    brand: str
    database_url: str
    panel_url: str
    panel_username: str
    panel_api_key: str


_current_tenant: ContextVar[TenantRuntime | None] = ContextVar("pasarguard_current_tenant", default=None)


def get_current_tenant() -> TenantRuntime | None:
    return _current_tenant.get()


def is_representative_runtime() -> bool:
    return _current_tenant.get() is not None


@contextmanager
def tenant_context(tenant: TenantRuntime) -> Iterator[TenantRuntime]:
    token = _current_tenant.set(tenant)
    try:
        yield tenant
    finally:
        _current_tenant.reset(token)

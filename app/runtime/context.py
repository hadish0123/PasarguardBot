from __future__ import annotations

from contextvars import ContextVar


_current_tenant: ContextVar[str | None] = ContextVar("current_tenant", default=None)


def set_tenant(tenant_id: str | None):
    return _current_tenant.set(tenant_id)


def reset_tenant(token) -> None:
    _current_tenant.reset(token)


def get_tenant() -> str | None:
    return _current_tenant.get()


def require_tenant() -> str:
    tenant = get_tenant()
    if not tenant:
        raise RuntimeError("Tenant context is required")
    return tenant

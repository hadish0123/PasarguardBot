from __future__ import annotations

from contextlib import asynccontextmanager

from app.runtime.context import reset_tenant, set_tenant


@asynccontextmanager
async def tenant_dispatch(tenant_id: str | None):
    token = set_tenant(tenant_id)
    try:
        yield
    finally:
        reset_tenant(token)

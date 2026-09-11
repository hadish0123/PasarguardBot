from __future__ import annotations

from contextlib import asynccontextmanager
from functools import wraps

from app.runtime.context import reset_tenant, set_tenant


@asynccontextmanager
async def tenant_dispatch(tenant_id: str | None):
    token = set_tenant(tenant_id)
    try:
        yield
    finally:
        reset_tenant(token)


def tenant_handler(tenant_id_getter):
    """Wrap a Telegram handler so every DB operation has an explicit tenant context."""
    def decorator(handler):
        @wraps(handler)
        async def wrapped(event, *args, **kwargs):
            tenant_id = tenant_id_getter()
            async with tenant_dispatch(tenant_id):
                return await handler(event, *args, **kwargs)
        return wrapped
    return decorator

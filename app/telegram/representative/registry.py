from __future__ import annotations

import asyncio

from app.telegram.representative.runtime import RepresentativeRuntime


class RepresentativeRuntimeRegistry:
    """Keeps exactly one live Telegram runtime per active tenant."""

    def __init__(self) -> None:
        self._runtimes: dict[str, RepresentativeRuntime] = {}
        self._lock = asyncio.Lock()

    async def start(self, tenant_id: str, bot_token: str) -> RepresentativeRuntime:
        async with self._lock:
            current = self._runtimes.get(tenant_id)
            if current is not None and current.is_running:
                return current
            runtime = RepresentativeRuntime(tenant_id, bot_token)
            await runtime.start()
            self._runtimes[tenant_id] = runtime
            return runtime

    async def stop(self, tenant_id: str) -> None:
        async with self._lock:
            runtime = self._runtimes.pop(tenant_id, None)
            if runtime is not None:
                await runtime.stop()

    def get(self, tenant_id: str) -> RepresentativeRuntime | None:
        return self._runtimes.get(tenant_id)

    def is_running(self, tenant_id: str) -> bool:
        runtime = self._runtimes.get(tenant_id)
        return bool(runtime and runtime.is_running)


registry = RepresentativeRuntimeRegistry()

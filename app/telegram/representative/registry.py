from __future__ import annotations

import asyncio
import hashlib

from app.telegram.representative.runtime import RepresentativeRuntime


class RepresentativeRuntimeRegistry:
    """Keeps exactly one live Telegram runtime and one token owner per tenant."""

    def __init__(self) -> None:
        self._runtimes: dict[str, RepresentativeRuntime] = {}
        self._token_owners: dict[str, str] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _token_key(bot_token: str) -> str:
        return hashlib.sha256(bot_token.strip().encode("utf-8")).hexdigest()

    async def start(self, tenant_id: str, bot_token: str) -> RepresentativeRuntime:
        token_key = self._token_key(bot_token)
        async with self._lock:
            current = self._runtimes.get(tenant_id)
            if current is not None and current.is_running:
                return current

            owner = self._token_owners.get(token_key)
            if owner is not None and owner != tenant_id:
                raise RuntimeError(
                    f"Telegram bot token is already owned by another representative runtime: {owner}"
                )

            runtime = RepresentativeRuntime(tenant_id, bot_token)
            await runtime.start()
            self._runtimes[tenant_id] = runtime
            self._token_owners[token_key] = tenant_id
            return runtime

    async def stop(self, tenant_id: str) -> None:
        async with self._lock:
            runtime = self._runtimes.pop(tenant_id, None)
            if runtime is not None:
                self._token_owners.pop(self._token_key(runtime.bot_token), None)
                await runtime.stop()

    def get(self, tenant_id: str) -> RepresentativeRuntime | None:
        return self._runtimes.get(tenant_id)

    def is_running(self, tenant_id: str) -> bool:
        runtime = self._runtimes.get(tenant_id)
        return bool(runtime and runtime.is_running)


registry = RepresentativeRuntimeRegistry()

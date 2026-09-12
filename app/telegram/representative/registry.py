from __future__ import annotations

import asyncio
import hashlib

from app.telegram.representative.runtime import RepresentativeRuntime


class RepresentativeRuntimeRegistry:
    """Keeps one live Telegram runtime and one token owner per tenant.

    Network startup/stop is deliberately performed outside the registry lock so
    one slow or broken bot cannot block every other representative bot.
    """

    def __init__(self) -> None:
        self._runtimes: dict[str, RepresentativeRuntime] = {}
        self._token_owners: dict[str, str] = {}
        self._starting: set[str] = set()
        self._lock = asyncio.Lock()

    @staticmethod
    def _token_key(bot_token: str) -> str:
        return hashlib.sha256(bot_token.strip().encode("utf-8")).hexdigest()

    async def start(self, tenant_id: str, bot_token: str) -> RepresentativeRuntime:
        token = bot_token.strip()
        if not token:
            raise ValueError("bot token is empty")
        token_key = self._token_key(token)

        async with self._lock:
            current = self._runtimes.get(tenant_id)
            if current is not None and current.is_running:
                return current

            owner = self._token_owners.get(token_key)
            if owner is not None and owner != tenant_id:
                raise RuntimeError(
                    f"Telegram bot token is already owned by another representative runtime: {owner}"
                )
            if tenant_id in self._starting:
                raise RuntimeError("representative bot is already starting")

            # Reserve the tenant/token before doing network I/O.
            self._starting.add(tenant_id)
            self._token_owners[token_key] = tenant_id

        runtime = RepresentativeRuntime(tenant_id, token)
        try:
            await runtime.start()
        except Exception:
            async with self._lock:
                self._starting.discard(tenant_id)
                if self._token_owners.get(token_key) == tenant_id:
                    self._token_owners.pop(token_key, None)
            raise

        async with self._lock:
            self._starting.discard(tenant_id)
            self._runtimes[tenant_id] = runtime
        return runtime

    async def stop(self, tenant_id: str) -> None:
        async with self._lock:
            runtime = self._runtimes.pop(tenant_id, None)
            self._starting.discard(tenant_id)
            if runtime is not None:
                self._token_owners.pop(self._token_key(runtime.bot_token), None)

        # Never hold the global registry lock while waiting for Telegram.
        if runtime is not None:
            await runtime.stop()

    def get(self, tenant_id: str) -> RepresentativeRuntime | None:
        return self._runtimes.get(tenant_id)

    def is_running(self, tenant_id: str) -> bool:
        runtime = self._runtimes.get(tenant_id)
        return bool(runtime and runtime.is_running)


registry = RepresentativeRuntimeRegistry()

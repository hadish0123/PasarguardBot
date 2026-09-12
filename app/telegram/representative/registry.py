from __future__ import annotations

import asyncio
import hashlib
import logging

from app.telegram.representative.runtime import RepresentativeRuntime

logger = logging.getLogger(__name__)


def _token_fingerprint(token: str) -> str:
    """Return safe token identifier for logging: hash_prefix + length."""
    if not token:
        return "none"
    h = hashlib.sha256(token.encode()).hexdigest()[:8]
    return f"{h}...{len(token)}"


class RepresentativeRuntimeRegistry:
    """Keeps exactly one live Telegram runtime per active tenant with exclusive polling ownership."""

    def __init__(self) -> None:
        self._runtimes: dict[str, RepresentativeRuntime] = {}
        self._polling_owners: dict[str, str] = {}  # token_fingerprint -> tenant_id
        self._lock = asyncio.Lock()

    async def start(self, tenant_id: str, bot_token: str) -> RepresentativeRuntime:
        async with self._lock:
            current = self._runtimes.get(tenant_id)
            if current is not None and current.is_running:
                return current
            
            # Check for token ownership conflicts
            fingerprint = _token_fingerprint(bot_token)
            existing_owner = self._polling_owners.get(fingerprint)
            if existing_owner and existing_owner != tenant_id:
                logger.critical(
                    "POLLING_CONFLICT: tenant_id=%s token_fingerprint=%s already owned by tenant_id=%s",
                    tenant_id, fingerprint, existing_owner
                )
                raise RuntimeError(
                    f"Token polling conflict: tenant {tenant_id} cannot start, token owned by {existing_owner}"
                )
            
            runtime = RepresentativeRuntime(tenant_id, bot_token)
            try:
                await runtime.start()  # Connect and register handlers, DO NOT poll yet
                self._runtimes[tenant_id] = runtime
                self._polling_owners[fingerprint] = tenant_id
                logger.info(
                    "RUNTIME_STARTED: tenant_id=%s token_fingerprint=%s",
                    tenant_id, fingerprint
                )
                return runtime
            except Exception as exc:
                logger.exception("Failed to start runtime for tenant %s: %s", tenant_id, exc)
                raise

    async def stop(self, tenant_id: str) -> None:
        async with self._lock:
            runtime = self._runtimes.pop(tenant_id, None)
            if runtime is not None:
                fingerprint = _token_fingerprint(runtime.bot_token)
                self._polling_owners.pop(fingerprint, None)
                await runtime.stop()
                logger.info(
                    "RUNTIME_STOPPED: tenant_id=%s token_fingerprint=%s",
                    tenant_id, fingerprint
                )

    def get(self, tenant_id: str) -> RepresentativeRuntime | None:
        return self._runtimes.get(tenant_id)

    def is_running(self, tenant_id: str) -> bool:
        runtime = self._runtimes.get(tenant_id)
        return bool(runtime and runtime.is_running)

    def is_polling_owner(self, tenant_id: str) -> bool:
        """Check if this tenant owns polling for its token."""
        runtime = self._runtimes.get(tenant_id)
        if not runtime:
            return False
        fingerprint = _token_fingerprint(runtime.bot_token)
        return self._polling_owners.get(fingerprint) == tenant_id


registry = RepresentativeRuntimeRegistry()

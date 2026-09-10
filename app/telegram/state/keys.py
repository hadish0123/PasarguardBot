"""Redis key builders for Telegram conversation state."""

from __future__ import annotations

import hashlib
from functools import lru_cache

from config import BOT_TOKEN, REDIS_NAMESPACE_PREFIX


def _runtime_namespace() -> str:
    from app.runtime.context import get_current_tenant

    tenant = get_current_tenant()
    if tenant is not None:
        return f"{REDIS_NAMESPACE_PREFIX.strip().rstrip(':') or 'bot'}:tenant:{tenant.registration_id}"
    return ""


@lru_cache(maxsize=1)
def get_redis_namespace() -> str:
    prefix = REDIS_NAMESPACE_PREFIX.strip()
    if prefix:
        return prefix.rstrip(":")
    token_hash = hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:16]
    return f"bot:{token_hash}"


def _namespace() -> str:
    return _runtime_namespace() or get_redis_namespace()


def build_state_key(user_id: int) -> str:
    return f"{_namespace()}:user:{user_id}"


def build_callback_key(token: str) -> str:
    return f"{_namespace()}:callback:{token}"


def build_lock_key(user_id: int, lock_name: str) -> str:
    return f"{_namespace()}:lock:{user_id}:{lock_name}"


def build_cache_key(key: str) -> str:
    return f"{_namespace()}:cache:{key}"


def build_direct_pay_user_key(user_id: int) -> str:
    return f"{_namespace()}:direct_pay:user:{user_id}"


def build_direct_pay_claim_key(user_id: int) -> str:
    return f"{_namespace()}:direct_pay:user:{user_id}:claim"


def build_direct_pay_tx_key(transaction_id: int) -> str:
    return f"{_namespace()}:direct_pay:tx:{transaction_id}"


def build_direct_pay_crypto_key(order_id: int) -> str:
    return f"{_namespace()}:direct_pay:crypto:{order_id}"

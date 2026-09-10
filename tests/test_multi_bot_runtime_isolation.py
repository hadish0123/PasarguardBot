import ast
from pathlib import Path

import pytest

from app.runtime.context import TenantRuntime, get_current_tenant, tenant_context
from app.telegram.state.keys import build_state_key


ROOT = Path(__file__).resolve().parents[1]


def tenant(registration_id: int, owner: int, bot_id: int) -> TenantRuntime:
    return TenantRuntime(
        registration_id=registration_id,
        owner_user_id=owner,
        bot_id=bot_id,
        bot_username=f"bot{bot_id}",
        brand=f"Brand {registration_id}",
        database_url=f"sqlite+aiosqlite:///tenant_{registration_id}.db",
        panel_url="https://panel.example",
        panel_username="admin",
        panel_api_key="secret",
    )


def test_context_isolation_and_redis_namespace():
    a, b = tenant(101, 1001, 2001), tenant(202, 1002, 2002)
    with tenant_context(a):
        key_a = build_state_key(55)
        assert get_current_tenant().registration_id == 101
    with tenant_context(b):
        key_b = build_state_key(55)
        assert get_current_tenant().registration_id == 202
    assert key_a != key_b
    assert ":tenant:101:" in key_a
    assert ":tenant:202:" in key_b
    assert get_current_tenant() is None


@pytest.mark.asyncio
async def test_context_does_not_leak_between_concurrent_tasks():
    import asyncio

    a, b = tenant(1, 10, 100), tenant(2, 20, 200)

    async def read(t):
        with tenant_context(t):
            await asyncio.sleep(0)
            return get_current_tenant().registration_id

    assert await asyncio.gather(read(a), read(b)) == [1, 2]
    assert get_current_tenant() is None


def test_provisioner_contains_no_per_service_creation():
    source = (ROOT / "app/services/representative_provisioner.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "serviceCreate" not in source
    assert "serviceInstanceDeployV2" not in source
    assert "serviceDomainCreate" not in source
    assert "command" in names


def test_multi_bot_manager_has_single_service_model():
    source = (ROOT / "app/services/multi_bot_manager.py").read_text(encoding="utf-8")
    assert "MultiBotManager" in source
    assert "start_for_registration" in source
    assert "tenant_context" in source
    assert "clone_handlers_from" not in source or "_handlers" in source

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pasarguard_runtime_context_test", ROOT / "app/runtime/context.py")
_context = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _context
assert _spec.loader is not None
_spec.loader.exec_module(_context)
TenantRuntime = _context.TenantRuntime
get_current_tenant = _context.get_current_tenant
tenant_context = _context.tenant_context


def tenant(registration_id: int, owner: int, bot_id: int) -> TenantRuntime:
    return TenantRuntime(registration_id, owner, bot_id, f"bot{bot_id}", f"Brand {registration_id}", f"sqlite+aiosqlite:///tenant_{registration_id}.db", "https://panel.example", "admin", "secret")


def test_context_isolation():
    a, b = tenant(101, 1001, 2001), tenant(202, 1002, 2002)
    with tenant_context(a):
        assert get_current_tenant().registration_id == 101
    with tenant_context(b):
        assert get_current_tenant().registration_id == 202
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


@pytest.mark.asyncio
async def test_global_kenzo_routes_api_calls_to_active_representative_client():
    from app import Kenzo
    from app.runtime.context import client_context

    class FakeRepresentativeClient:
        def __init__(self):
            self.calls = []

        async def send_message(self, entity=None, message=None, **kwargs):
            self.calls.append((entity, message, kwargs))
            return "representative-message"

    representative = FakeRepresentativeClient()
    with client_context(representative):
        result = await Kenzo.send_message(123, "سلام نماینده")

    assert result == "representative-message"
    assert representative.calls == [(123, "سلام نماینده", {})]


def test_provisioner_contains_no_per_service_creation():
    source = (ROOT / "app/services/representative_provisioner.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "serviceCreate" not in source
    assert "serviceInstanceDeployV2" not in source
    assert "serviceDomainCreate" not in source
    assert "command" in names


def test_multi_bot_manager_has_isolation_runtime():
    source = (ROOT / "app/services/multi_bot_manager.py").read_text(encoding="utf-8")
    assert "MultiBotManager" in source
    assert "start_for_registration" in source
    assert "tenant_context" in source
    assert "client_context" in source

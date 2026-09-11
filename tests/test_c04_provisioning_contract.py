from app.db.models import RegistrationStatus, TenantStatus
from app.rebuild.page_registry import get_page


def test_c04_page_contract_is_complete():
    page = get_page("C-04")
    assert page.title == "Representative Tenant Provisioning"
    assert "provision" in page.buttons
    assert "retry" in page.buttons
    assert "failed" in page.states
    assert "active" in page.states


def test_registration_lifecycle_has_failure_state():
    assert RegistrationStatus.PROVISIONING.value == "provisioning"
    assert RegistrationStatus.FAILED.value == "failed"
    assert RegistrationStatus.ACTIVE.value == "active"


def test_tenant_lifecycle_has_failure_and_active_states():
    assert TenantStatus.PROVISIONING.value == "provisioning"
    assert TenantStatus.FAILED.value == "failed"
    assert TenantStatus.ACTIVE.value == "active"

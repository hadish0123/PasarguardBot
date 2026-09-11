import pytest

from app.core.exceptions import ValidationError
from app.services.registration import RegistrationService


def test_brand_validation_accepts_normal_brand():
    assert RegistrationService.validate_brand("My Brand") == "My Brand"


def test_brand_validation_rejects_short_value():
    with pytest.raises(ValidationError):
        RegistrationService.validate_brand("x")


def test_panel_url_is_normalized():
    assert RegistrationService.normalize_panel_url("panel.example.com/dashboard/") == "https://panel.example.com"


def test_panel_url_rejects_spaces():
    with pytest.raises(ValidationError):
        RegistrationService.normalize_panel_url("https://panel example.com")

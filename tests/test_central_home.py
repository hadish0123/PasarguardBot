from types import SimpleNamespace

from app.telegram.central import home_text, registration_status_text


def test_home_text_contains_primary_actions():
    text = home_text()
    assert "سامانه مرکزی نمایندگان" in text
    assert "ثبت" in text
    assert "پیگیری" in text


def test_registration_status_text_for_active_request():
    record = SimpleNamespace(
        tracking_code="PG-AB12CD34",
        brand="Demo",
        status="active",
        rejection_reason=None,
    )
    text = registration_status_text(record)
    assert "PG-AB12CD34" in text
    assert "Demo" in text
    assert "فعال" in text


def test_registration_status_text_for_rejected_request_includes_reason():
    record = SimpleNamespace(
        tracking_code="PG-ZZ998877",
        brand=None,
        status="rejected",
        rejection_reason="اطلاعات پنل ناقص است",
    )
    text = registration_status_text(record)
    assert "رد شده" in text
    assert "اطلاعات پنل ناقص است" in text

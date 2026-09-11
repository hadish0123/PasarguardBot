from app.services.texts import DEFAULTS, LABELS

def test_a07_catalog_is_complete():
    assert set(LABELS) == set(DEFAULTS)
    assert all(DEFAULTS[key].strip() for key in LABELS)

def test_a07_expected_customer_buttons():
    for key in ("buy_button","services_button","wallet_button","profile_button","referral_button","discount_button","trial_button","support_button"):
        assert key in DEFAULTS

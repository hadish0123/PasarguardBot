from app.rebuild.page_registry import get_page


def test_a04_contract():
    page = get_page("A-04")
    assert page.title == "Sales and Order Management"
    assert {"list", "view", "confirm_payment", "fulfill", "cancel", "back"}.issubset(page.buttons)
    assert {"pending", "paid", "fulfilled", "cancelled"}.issubset(page.states)
    assert page.data_scope == "current tenant orders"

from app.rebuild.page_registry import get_page


def test_a02_contract():
    page = get_page("A-02")
    assert page.title == "Plan Management"
    assert {"add", "view", "toggle", "delete", "confirm_delete"}.issubset(page.buttons)
    assert "creating_price" in page.states
    assert page.data_scope == "current tenant plans"

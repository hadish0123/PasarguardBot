from app.rebuild.page_registry import get_page


def test_a03_contract():
    page = get_page("A-03")
    assert page.title == "Representative User Management"
    assert {"search", "view", "block", "unblock", "add_balance", "subtract_balance"}.issubset(page.buttons)
    assert "balance_input" in page.states
    assert page.permission == "active representative owner"
    assert page.data_scope == "current tenant users and balance ledger"

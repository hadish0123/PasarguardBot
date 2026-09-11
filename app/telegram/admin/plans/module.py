"""Shared plan helpers.

Plan management is owned by the representative runtime. This module remains
available for shared plan callback/message functions, but deliberately does
not register Telegram handlers itself so the central bot cannot expose plan
management.
"""

MODULE_NAME = "admin.plans"
MODULE_ENABLED = True
MODULE_ORDER = 1000
MODULE_DESCRIPTION = "Shared plan management helpers"


def setup(client):
    """Keep legacy module loading harmless; representative_panel owns routing."""
    return None

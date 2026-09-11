from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Area(StrEnum):
    CENTRAL = "central"
    ADMIN = "representative_admin"
    USER = "representative_user"


@dataclass(frozen=True, slots=True)
class PageSpec:
    id: str
    area: Area
    title: str
    purpose: str
    entry: tuple[str, ...]
    buttons: tuple[str, ...]
    states: tuple[str, ...]
    permission: str
    data_scope: str
    dependencies: tuple[str, ...]


PAGES: tuple[PageSpec, ...] = (
    PageSpec("C-01", Area.CENTRAL, "Central Home", "Private entry point for representative registration and owner-scoped request tracking.", ("/start", "central:home"), ("register_representative", "track_registration", "track_latest", "cancel"), ("idle", "creating_request", "request_created", "tracking_input", "loading", "empty", "error"), "private Telegram chat; owner-scoped records", "central database", ("SQLAlchemy", "Telethon")),
    PageSpec("C-02", Area.CENTRAL, "Representative Registration Wizard", "Collect and validate bot and Pasarguard credentials.", ("central:registration:continue", "C-01 register"), ("continue", "previous", "confirm", "cancel"), ("brand", "bot_token", "bot_id", "panel_url", "panel_username", "panel_api_key", "review", "pending", "error"), "private Telegram chat; owner-scoped draft", "central database", ("Telegram Bot API", "Pasarguard API", "Fernet", "SQLAlchemy")),
    PageSpec("C-03", Area.CENTRAL, "Central Admin Review", "Review pending representative requests and approve or reject them.", ("/admin", "central:admin:pending", "central:admin:view"), ("pending", "view", "approve", "reject", "back"), ("loading", "ready", "empty", "detail", "provisioning", "rejected", "error"), "central admin IDs only", "central database", ("SQLAlchemy", "Telethon")),
    PageSpec("A-01", Area.ADMIN, "Representative Dashboard", "Representative owner dashboard and entry point to tenant administration.", ("/start", "main_menu"), ("plans", "users", "sales", "discounts", "texts", "logs", "links", "settings", "support"), ("loading", "ready", "empty", "error"), "representative owner", "tenant database", ("tenant runtime", "Pasarguard API", "Redis")),
    PageSpec("U-01", Area.USER, "Representative User Home", "Customer entry point for browsing and purchasing services.", ("/start",), ("buy", "my_services", "wallet", "profile", "referral", "trial", "support"), ("loading", "ready", "empty", "error"), "any customer in a representative bot", "current tenant", ("tenant runtime", "Pasarguard API")),
)


def get_page(page_id: str) -> PageSpec:
    for page in PAGES:
        if page.id == page_id:
            return page
    raise KeyError(f"Unknown page: {page_id}")

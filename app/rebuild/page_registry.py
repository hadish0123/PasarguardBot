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
    PageSpec(
        id="C-01",
        area=Area.CENTRAL,
        title="Central Home",
        purpose="Private entry point for representative registration and owner-scoped request tracking.",
        entry=("/start", "central:home"),
        buttons=("register_representative", "track_registration", "track_latest", "cancel"),
        states=("idle", "creating_request", "request_created", "tracking_input", "loading", "empty", "error"),
        permission="private Telegram chat; each user may only read their own registration records",
        data_scope="central database, owner_id scoped for registration reads",
        dependencies=("SQLAlchemy", "PostgreSQL-compatible DATABASE_URL", "Telethon"),
    ),
    PageSpec(
        id="C-02",
        area=Area.CENTRAL,
        title="Representative Registration Wizard",
        purpose="Collect, validate and securely persist the bot and Pasarguard panel credentials required to submit a representative request.",
        entry=("central:registration:continue", "C-01 register"),
        buttons=("continue", "previous", "confirm", "cancel"),
        states=("brand", "bot_token", "bot_id", "panel_url", "panel_username", "panel_api_key", "review", "pending", "error"),
        permission="private Telegram chat; current owner can edit only their draft",
        data_scope="central database, owner-scoped draft",
        dependencies=("Telegram Bot API", "Pasarguard API", "Fernet SECRET_KEY", "SQLAlchemy", "Telethon"),
    ),
    PageSpec(
        id="A-01",
        area=Area.ADMIN,
        title="Representative Dashboard",
        purpose="Representative owner dashboard and the single entry point to tenant administration.",
        entry=("/start", "main_menu"),
        buttons=("plans", "users", "sales", "discounts", "texts", "logs", "links", "settings", "support"),
        states=("loading", "ready", "empty", "error"),
        permission="representative owner",
        data_scope="tenant database",
        dependencies=("tenant runtime", "Pasarguard API", "Redis"),
    ),
    PageSpec(
        id="U-01",
        area=Area.USER,
        title="Representative User Home",
        purpose="Customer entry point for browsing and purchasing services.",
        entry=("/start",),
        buttons=("buy", "my_services", "wallet", "profile", "referral", "trial", "support"),
        states=("loading", "ready", "empty", "error"),
        permission="any customer inside a representative bot",
        data_scope="current representative tenant",
        dependencies=("tenant runtime", "Pasarguard API"),
    ),
)


def get_page(page_id: str) -> PageSpec:
    for page in PAGES:
        if page.id == page_id:
            return page
    raise KeyError(f"Unknown page: {page_id}")

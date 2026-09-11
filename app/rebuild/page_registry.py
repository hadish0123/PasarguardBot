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


# Page A-01 is the first page being implemented. Every later page is added
# only after this page's contract is complete and verified.
PAGES: tuple[PageSpec, ...] = (
    PageSpec(
        id="C-01",
        area=Area.CENTRAL,
        title="Central Home",
        purpose="Central bot entry point for representative lifecycle management.",
        entry=("/start",),
        buttons=("register_representative", "track_registration"),
        states=("idle", "registration_pending", "no_active_registration"),
    ),
    PageSpec(
        id="A-01",
        area=Area.ADMIN,
        title="Representative Dashboard",
        purpose="Representative owner dashboard and the single entry point to tenant administration.",
        entry=("/start", "main_menu"),
        buttons=("plans", "users", "sales", "discounts", "texts", "logs", "links", "settings", "support"),
        states=("loading", "ready", "empty", "error"),
    ),
    PageSpec(
        id="U-01",
        area=Area.USER,
        title="Representative User Home",
        purpose="Customer entry point for browsing and purchasing services.",
        entry=("/start",),
        buttons=("buy", "my_services", "wallet", "profile", "referral", "trial", "support"),
        states=("loading", "ready", "empty", "error"),
    ),
)


def get_page(page_id: str) -> PageSpec:
    for page in PAGES:
        if page.id == page_id:
            return page
    raise KeyError(f"Unknown page: {page_id}")

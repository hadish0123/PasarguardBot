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
    PageSpec("C-03", Area.CENTRAL, "Central Admin Review", "Review pending representative requests and approve or reject them.", ("/admin", "central:admin:pending", "central:admin:view"), ("pending", "view", "approve", "reject", "retry", "back"), ("loading", "ready", "empty", "detail", "provisioning", "active", "failed", "rejected", "error"), "central admin IDs only", "central database", ("SQLAlchemy", "Telethon", "ProvisioningService")),
    PageSpec("C-04", Area.CENTRAL, "Representative Tenant Provisioning", "Create an isolated tenant identity, persist encrypted credentials, start its dedicated Telegram runtime, verify the bot identity, and activate the tenant.", ("C-03 approve", "C-03 retry"), ("provision", "retry", "back"), ("provisioning", "runtime_starting", "runtime_ready", "active", "failed", "retrying"), "central admin lifecycle; tenant owner notified on success", "central tenant registry with tenant-scoped runtime", ("SQLAlchemy", "Fernet", "Telethon", "TenantService", "RepresentativeRuntimeRegistry")),
    PageSpec("A-01", Area.ADMIN, "Representative Dashboard", "Active representative owner dashboard and gateway to tenant administration.", ("/start", "/admin", "rep:rep.home"), ("plans", "users", "orders", "discounts", "sales", "texts", "logs", "links", "settings"), ("loading", "ready", "error"), "active representative owner", "current tenant", ("tenant runtime", "RepresentativeDashboardService")),
    PageSpec("A-02", Area.ADMIN, "Plan Management", "Create, inspect, enable/disable, and delete tenant-scoped sales plans.", ("A-01 plans", "rep:plans"), ("list", "add", "cancel", "view", "toggle", "delete", "confirm_delete", "back"), ("empty", "listing", "creating_name", "creating_volume", "creating_days", "creating_price", "created", "confirm_delete", "error"), "active representative owner", "current tenant plans", ("SQLAlchemy", "PlanService", "tenant runtime")),
    PageSpec("A-03", Area.ADMIN, "Representative User Management", "Search, inspect, block/unblock, and adjust the balance of tenant customers with an auditable wallet ledger.", ("A-01 users", "rep:users:list", "rep:users:search"), ("list", "search", "view", "block", "unblock", "add_balance", "subtract_balance", "cancel", "back"), ("empty", "listing", "searching", "detail", "balance_input", "blocked", "active", "updated", "error"), "active representative owner", "current tenant users and balance ledger", ("SQLAlchemy", "RepresentativeUserService", "UserBalanceLog", "tenant runtime")),
    PageSpec("U-01", Area.USER, "Representative User Home", "Customer entry point for browsing and purchasing services.", ("/start",), ("buy", "my_services", "wallet", "profile", "referral", "trial", "support"), ("loading", "ready", "empty", "blocked", "error"), "any non-owner customer in a representative bot", "current tenant", ("tenant runtime", "RepresentativeUser", "Pasarguard API")),
)


def get_page(page_id: str) -> PageSpec:
    for page in PAGES:
        if page.id == page_id:
            return page
    raise KeyError(f"Unknown page: {page_id}")

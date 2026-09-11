from enum import StrEnum


class RegistrationStep(StrEnum):
    BRAND = "brand"
    BOT_TOKEN = "bot_token"
    BOT_ID = "bot_id"
    PANEL_URL = "panel_url"
    PANEL_USERNAME = "panel_username"
    PANEL_API_KEY = "panel_api_key"
    AWAITING_ADMIN = "awaiting_admin"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    REJECTED = "rejected"

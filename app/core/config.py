from __future__ import annotations

import os


class Settings:
    """Centralized runtime configuration."""

    telegram_api_id: int = int(os.getenv("API_ID", "0"))
    telegram_api_hash: str = os.getenv("API_HASH", "")
    central_bot_token: str = os.getenv("BOT_TOKEN", "")
    database_url: str = os.getenv("SQLALCHEMY_DATABASE_URL") or os.getenv("DATABASE_URL", "")
    redis_url: str = os.getenv("REDIS_URL", "")
    fastapi_port: int = int(os.getenv("FASTAPI_PORT", os.getenv("FAST_API_PORT", "8080")))
    admin_ids: tuple[int, ...] = tuple(
        int(x.strip()) for x in os.getenv("ADMIN_ID", "").split(",") if x.strip().isdigit()
    )


settings = Settings()

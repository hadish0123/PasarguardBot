from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.services.central_registry import get_by_id, reveal
from config import SQLALCHEMY_DATABASE_URL


def _db_name(registration_id: int) -> str:
    return f"primevpn_rep_{registration_id}"


def tenant_database_url(database: str) -> str:
    return make_url(SQLALCHEMY_DATABASE_URL).set(database=database).render_as_string(hide_password=False)


async def _create_database(database: str) -> None:
    root_url = os.getenv("MYSQL_ROOT_URL", "").strip() or SQLALCHEMY_DATABASE_URL
    parsed = make_url(root_url).set(database="mysql")
    import asyncmy

    conn = await asyncmy.connect(
        host=parsed.host,
        port=parsed.port or 3306,
        user=parsed.username,
        password=parsed.password,
        database="mysql",
        autocommit=True,
    )
    try:
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "", database)
        async with conn.cursor() as cursor:
            await cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{safe_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        conn.close()


def _upgrade_sync(database_url: str) -> None:
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.attributes["database_url"] = database_url
    command.upgrade(cfg, "head")


async def migrate_tenant_database(database_url: str) -> None:
    await asyncio.to_thread(_upgrade_sync, database_url)


async def provision_representative(registration_id: int) -> dict:
    registration = await get_by_id(registration_id)
    if not registration:
        raise RuntimeError("Registration not found")

    database = _db_name(registration_id)
    await _create_database(database)
    database_url = tenant_database_url(database)
    await migrate_tenant_database(database_url)

    reveal(registration["bot_token"])
    reveal(registration["panel_api_key"])

    return {
        "tenant_db_name": database,
        "railway_service_id": os.getenv("RAILWAY_SERVICE_ID", "").strip() or None,
        "railway_environment_id": os.getenv("RAILWAY_ENVIRONMENT_ID", "").strip() or None,
    }

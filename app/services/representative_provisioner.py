from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL
from sqlalchemy.engine import make_url

from app.services.central_registry import get_by_id, reveal
from config import SQLALCHEMY_DATABASE_URL


def _db_name(registration_id: int) -> str:
    return f"primevpn_rep_{registration_id}"


def tenant_database_url(database: str) -> str:
    return make_url(SQLALCHEMY_DATABASE_URL).set(database=database).render_as_string(hide_password=False)


def _root_database_url() -> str:
    """Build a real root URL when Railway did not provide a usable MYSQL_ROOT_URL.

    The application user must not need global CREATE/DROP privileges. The root
    connection is used only during tenant provisioning to create the tenant DB
    and grant that DB to the normal application account.
    """
    explicit = os.getenv("MYSQL_ROOT_URL", "").strip()
    root_password = os.getenv("MARIADB_ROOT_PASSWORD", "").strip()
    host = (os.getenv("MYSQLHOST_PRIVATE", "").strip() or os.getenv("MYSQLHOST", "").strip())
    port = (os.getenv("MYSQLPORT_PRIVATE", "").strip() or os.getenv("MYSQLPORT", "").strip())

    # A URL explicitly configured with a root account is authoritative.
    if explicit:
        try:
            parsed = make_url(explicit)
            if (parsed.username or "").strip().lower() == "root":
                return explicit
        except Exception:
            pass

    if root_password and host:
        return URL.create(
            "mysql+asyncmy",
            username="root",
            password=root_password,
            host=host,
            port=int(port) if port else 3306,
            database="mysql",
        ).render_as_string(hide_password=False)

    if explicit:
        return explicit
    return SQLALCHEMY_DATABASE_URL


async def _create_database(database: str) -> None:
    root_url = _root_database_url()
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
        if safe_name != database or not safe_name:
            raise ValueError("Invalid tenant database name")

        app_url = make_url(SQLALCHEMY_DATABASE_URL)
        app_user = str(app_url.username or "").strip()
        if not app_user:
            raise RuntimeError("SQLALCHEMY_DATABASE_URL does not contain an application database user")
        safe_user = app_user.replace("`", "``").replace("'", "''")

        async with conn.cursor() as cursor:
            await cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{safe_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            # The application account is intentionally granted access only to
            # this tenant DB, keeping representative data isolated by database.
            await cursor.execute(
                f"GRANT ALL PRIVILEGES ON `{safe_name}`.* TO '{safe_user}'@'%'"
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

from __future__ import annotations

from sqlalchemy import text

from app.db.base import AsyncSessionLocal
from app.utils.security.crypto import decrypt_data, encrypt_data

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bot_registrations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tracking_code VARCHAR(32) NOT NULL UNIQUE,
    owner_user_id BIGINT NOT NULL,
    brand VARCHAR(120) NOT NULL,
    bot_id BIGINT NULL UNIQUE,
    bot_username VARCHAR(255) NULL,
    bot_token TEXT NOT NULL,
    panel_url VARCHAR(512) NOT NULL,
    panel_username VARCHAR(255) NOT NULL,
    panel_api_key TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    step VARCHAR(32) NOT NULL DEFAULT 'brand',
    rejection_reason TEXT NULL,
    tenant_db_name VARCHAR(64) NULL,
    railway_service_id VARCHAR(128) NULL,
    railway_environment_id VARCHAR(128) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    approved_at DATETIME NULL
)
"""


def _row(row) -> dict:
    return dict(row._mapping)


async def ensure_registry() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(text(CREATE_TABLE_SQL))
        # Safe upgrades for databases created by the first development revision.
        columns = {
            row[0]
            for row in (await session.execute(text("SHOW COLUMNS FROM bot_registrations"))).all()
        }
        for name, ddl in (
            ("railway_service_id", "ALTER TABLE bot_registrations ADD COLUMN railway_service_id VARCHAR(128) NULL"),
            ("railway_environment_id", "ALTER TABLE bot_registrations ADD COLUMN railway_environment_id VARCHAR(128) NULL"),
        ):
            if name not in columns:
                await session.execute(text(ddl))
        await session.commit()


async def get_active_for_owner(owner_user_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT * FROM bot_registrations "
                "WHERE owner_user_id=:owner AND status IN ('draft','pending','approved') "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"owner": owner_user_id},
        )
        row = result.first()
        return _row(row) if row else None


async def create_draft(owner_user_id: int, tracking_code: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                "INSERT INTO bot_registrations "
                "(tracking_code, owner_user_id, brand, bot_id, bot_token, panel_url, panel_username, panel_api_key, status, step) "
                "VALUES (:tracking,:owner,'',NULL,'','','','', 'draft','brand')"
            ),
            {"tracking": tracking_code, "owner": owner_user_id},
        )
        await session.commit()
        return int(result.lastrowid)


async def get_by_id(registration_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT * FROM bot_registrations WHERE id=:id LIMIT 1"), {"id": registration_id}
        )
        row = result.first()
        return _row(row) if row else None


async def update_registration(registration_id: int, **values) -> None:
    allowed = {
        "brand",
        "bot_id",
        "bot_username",
        "bot_token",
        "panel_url",
        "panel_username",
        "panel_api_key",
        "status",
        "step",
        "rejection_reason",
        "tenant_db_name",
        "railway_service_id",
        "railway_environment_id",
        "approved_at",
    }
    values = {key: value for key, value in values.items() if key in allowed}
    if not values:
        return
    assignments: list[str] = []
    params: dict[str, object] = {"id": registration_id}
    for key, value in values.items():
        assignments.append(f"{key}=:{key}")
        params[key] = value
    assignments.append("updated_at=CURRENT_TIMESTAMP")
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(f"UPDATE bot_registrations SET {', '.join(assignments)} WHERE id=:id"), params
        )
        await session.commit()


async def get_approved():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT * FROM bot_registrations WHERE status='approved' ORDER BY id ASC")
        )
        return [_row(row) for row in result.fetchall()]


def protect(value: str) -> str:
    return encrypt_data(value)


def reveal(value: str) -> str:
    return decrypt_data(value)

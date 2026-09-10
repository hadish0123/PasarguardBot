from __future__ import annotations

import os
import re
from urllib.parse import quote_plus, urlsplit, urlunsplit

import httpx
from sqlalchemy.engine import make_url

from app.services.central_registry import get_by_id, reveal
from config import SQLALCHEMY_DATABASE_URL

RAILWAY_ENDPOINT = "https://backboard.railway.com/graphql/v2"
REPO = "hadish0123/PasarguardBot"


def _db_name(registration_id: int) -> str:
    return f"primevpn_rep_{registration_id}"


def _railway_token() -> str:
    token = os.getenv("RAILWAY_AUTOMATION_TOKEN", "").strip()
    if not token:
        raise RuntimeError("RAILWAY_AUTOMATION_TOKEN is not configured")
    return token


def _db_url(database: str) -> str:
    parsed = make_url(SQLALCHEMY_DATABASE_URL)
    parsed = parsed.set(database=database)
    return parsed.render_as_string(hide_password=False)


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


async def _graphql(query: str, variables: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            RAILWAY_ENDPOINT,
            headers={"Authorization": f"Bearer {_railway_token()}", "Content-Type": "application/json"},
            json={"query": query, "variables": variables},
        )
        response.raise_for_status()
        payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"]))
    return payload["data"]


async def provision_representative(registration_id: int) -> dict:
    registration = await get_by_id(registration_id)
    if not registration:
        raise RuntimeError("Registration not found")

    project_id = os.getenv("RAILWAY_PROJECT_ID", "").strip()
    environment_id = os.getenv("RAILWAY_ENVIRONMENT_ID", "").strip()
    if not project_id or not environment_id:
        raise RuntimeError("Railway project/environment IDs are not available")

    database = _db_name(registration_id)
    await _create_database(database)

    token = reveal(registration["bot_token"])
    panel_api_key = reveal(registration["panel_api_key"])
    service_name = f"PRIMEVPN-{registration['brand'][:35]}".strip()

    service_data = await _graphql(
        """
        mutation CreateService($input: ServiceCreateInput!) {
          serviceCreate(input: $input) { id name }
        }
        """,
        {
            "input": {
                "projectId": project_id,
                "environmentId": environment_id,
                "name": service_name,
                "branch": "main",
                "source": {"repo": REPO},
            }
        },
    )
    service_id = service_data["serviceCreate"]["id"]

    # Telegram Bot API needs only BOT_TOKEN. Numeric ADMIN_ID is the owner/admin
    # of this isolated representative instance. No API_ID/API_HASH/session is
    # created or copied to representative services.
    variables = {
        "BOT_TOKEN": token,
        "ADMIN_ID": str(registration["owner_user_id"]),
        "BOT_TAG": registration["brand"],
        "ADMIN_ID_TAG": str(registration["owner_user_id"]),
        "BOT_ROLE": "representative",
        "REPRESENTATIVE_ID": str(registration_id),
        "REP_PANEL_URL": registration["panel_url"],
        "REP_PANEL_USERNAME": registration["panel_username"],
        "REP_PANEL_API_KEY": panel_api_key,
        "SQLALCHEMY_DATABASE_URL": _db_url(database),
        "FASTAPI_PORT": "6160",
        "DISABLE_UPTIME_BUTTONS": "true",
    }

    for name, value in variables.items():
        await _graphql(
            """
            mutation UpsertVariable($input: VariableUpsertInput!) {
              variableUpsert(input: $input)
            }
            """,
            {
                "input": {
                    "projectId": project_id,
                    "environmentId": environment_id,
                    "serviceId": service_id,
                    "name": name,
                    "value": value,
                }
            },
        )

    await _graphql(
        """
        mutation Deploy($serviceId: String!, $environmentId: String!) {
          serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId)
        }
        """,
        {"serviceId": service_id, "environmentId": environment_id},
    )

    await _graphql(
        """
        mutation Domain($serviceId: String!, $environmentId: String!) {
          serviceDomainCreate(input: {serviceId: $serviceId, environmentId: $environmentId}) { id }
        }
        """,
        {"serviceId": service_id, "environmentId": environment_id},
    )

    return {
        "tenant_db_name": database,
        "railway_service_id": service_id,
        "railway_environment_id": environment_id,
    }

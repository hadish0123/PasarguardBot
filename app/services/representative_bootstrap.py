from __future__ import annotations

import os

from app.db.crud.panels import PanelsManager
from app.utils.security.crypto import encrypt_data


async def ensure_representative_panel() -> None:
    if os.getenv("BOT_ROLE", "central").strip().lower() != "representative":
        return

    panel_url = os.getenv("REP_PANEL_URL", "").strip()
    api_key = os.getenv("REP_PANEL_API_KEY", "").strip()
    username = os.getenv("REP_PANEL_USERNAME", "-").strip() or "-"
    brand = os.getenv("BOT_TAG", "Representative").strip() or "Representative"
    registration_id = os.getenv("REPRESENTATIVE_ID", "").strip()

    if not panel_url or not api_key or not registration_id:
        raise RuntimeError("Representative panel configuration is incomplete")

    code = int(registration_id)
    manager = PanelsManager()
    panel = await manager.get_panel_by_code(code)
    encrypted_placeholder = encrypt_data(api_key)

    if panel:
        await manager.update_panel(
            code,
            name=brand,
            enable=True,
            base_url=panel_url,
            username=username,
            password=encrypted_placeholder,
            cookie=api_key,
            auth_type="api_key",
        )
        return

    await manager.add_panel(
        code=code,
        name=brand,
        enable=True,
        base_url=panel_url,
        username=username,
        password=encrypted_placeholder,
        cookie=api_key,
        auth_type="api_key",
    )

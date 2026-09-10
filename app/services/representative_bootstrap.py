from __future__ import annotations

from app.db.crud.panels import PanelsManager
from app.utils.security.crypto import encrypt_data


async def ensure_representative_panel(registration: dict) -> None:
    """Create/update only this representative's panel inside its tenant DB."""
    panel_url = str(registration.get("panel_url") or "").strip()
    api_key = str(registration.get("panel_api_key") or "").strip()
    username = str(registration.get("panel_username") or "-").strip() or "-"
    brand = str(registration.get("brand") or "Representative").strip() or "Representative"
    registration_id = int(registration["id"])
    if not panel_url or not api_key:
        raise RuntimeError(f"Representative {registration_id} is missing panel credentials")

    manager = PanelsManager()
    panel = await manager.get_panel_by_code(registration_id)
    encrypted_placeholder = encrypt_data(api_key)
    if panel:
        await manager.update_panel(
            registration_id,
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
        code=registration_id,
        name=brand,
        enable=True,
        base_url=panel_url,
        username=username,
        password=encrypted_placeholder,
        cookie=api_key,
        auth_type="api_key",
    )

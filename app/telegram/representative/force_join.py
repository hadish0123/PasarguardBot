from __future__ import annotations

import aiohttp


class ForceJoinError(ValueError):
    pass


async def _api(token: str, method: str, payload: dict) -> dict:
    token = (token or "").strip()
    if not token:
        raise ForceJoinError("توکن ربات نماینده در دسترس نیست.")
    url = f"https://api.telegram.org/bot{token}/{method}"
    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as response:
            try:
                data = await response.json(content_type=None)
            except Exception:
                data = {"ok": False, "description": f"HTTP {response.status}"}
    if not data.get("ok"):
        description = str(data.get("description") or "Telegram API error")
        raise ForceJoinError(description)
    return data["result"]


async def get_bot(token: str) -> dict:
    return await _api(token, "getMe", {})


async def validate_channel_admin(token: str, channel_id: int) -> dict:
    """Resolve a channel and prove that this exact representative bot is admin."""
    chat = await _api(token, "getChat", {"chat_id": channel_id})
    if chat.get("type") != "channel":
        raise ForceJoinError("آیدی واردشده متعلق به یک کانال تلگرامی نیست.")

    bot = await get_bot(token)
    member = await _api(
        token,
        "getChatMember",
        {"chat_id": channel_id, "user_id": int(bot["id"])},
    )
    status = str(member.get("status") or "")
    if status not in {"administrator", "creator"}:
        raise ForceJoinError(
            "همین ربات نماینده داخل کانال ادمین نیست. ابتدا همین ربات را با دسترسی ادمین به کانال اضافه کنید."
        )

    return chat


async def is_user_member(token: str, channel_id: int, user_id: int) -> bool:
    """Check membership using Bot API so numeric -100 channel IDs never depend on Telethon access_hash cache."""
    try:
        member = await _api(
            token,
            "getChatMember",
            {"chat_id": channel_id, "user_id": int(user_id)},
        )
    except ForceJoinError:
        return False

    status = str(member.get("status") or "")
    if status in {"creator", "administrator", "member"}:
        return True
    if status == "restricted":
        return bool(member.get("is_member"))
    return False


def channel_url(chat: dict) -> str | None:
    username = str(chat.get("username") or "").strip()
    return f"https://t.me/{username}" if username else None

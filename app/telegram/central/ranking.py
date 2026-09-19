from __future__ import annotations

from sqlalchemy import func, select
from telethon import events

from app.db.models import RepresentativeUser, TenantRecord, TenantStatus
from app.db.session import SessionFactory


RANKING_PHRASES = {"رتبه بندی", "رتبه‌بندی", "رتبه بندی!"}


async def top_representatives(limit: int = 3):
    if SessionFactory is None:
        return []
    async with SessionFactory() as session:
        query = (
            select(
                TenantRecord.bot_username,
                TenantRecord.brand,
                TenantRecord.bot_id,
                func.count(RepresentativeUser.id).label("user_count"),
            )
            .join(
                RepresentativeUser,
                RepresentativeUser.tenant_id == TenantRecord.id,
                isouter=True,
            )
            .where(TenantRecord.status == TenantStatus.ACTIVE.value)
            .group_by(
                TenantRecord.id,
                TenantRecord.bot_username,
                TenantRecord.brand,
                TenantRecord.bot_id,
            )
            .order_by(
                func.count(RepresentativeUser.id).desc(),
                TenantRecord.bot_id.asc(),
            )
            .limit(limit)
        )
        rows = (await session.execute(query)).all()
        return [
            {
                "username": row.bot_username,
                "brand": row.brand,
                "bot_id": row.bot_id,
                "user_count": int(row.user_count or 0),
            }
            for row in rows
        ]


def _is_ranking(text: str) -> bool:
    normalized = " ".join((text or "").strip().split())
    return normalized in RANKING_PHRASES


def _is_group(event) -> bool:
    return not bool(getattr(event, "is_private", False))


def _bot_was_added(event) -> bool:
    payload = getattr(event, "_message_payload", {}) or {}
    members = payload.get("new_chat_members") or []
    me = getattr(event.client, "_me", None)
    bot_id = getattr(me, "id", None)
    return bool(
        bot_id
        and any(int(member.get("id", 0)) == int(bot_id) for member in members)
    )


def register_group_handlers(client) -> None:
    async def group_message(event):
        if not _is_group(event):
            return

        if _bot_was_added(event):
            try:
                await event.respond(
                    "✅ ربات مرکزی با موفقیت فعال شد.\n\n"
                    "برای مشاهده رتبه‌بندی نمایندگان، عبارت «رتبه بندی» را ارسال کنید."
                )
            except Exception:
                pass
            return

        if not _is_ranking(event.raw_text):
            return

        try:
            rows = await top_representatives(3)
        except Exception:
            await event.respond(
                "⚠️ دریافت رتبه‌بندی در حال حاضر ممکن نیست. "
                "لطفاً کمی بعد دوباره تلاش کنید."
            )
            return

        if not rows:
            await event.respond(
                "📊 هنوز اطلاعات کافی برای رتبه‌بندی نمایندگان ثبت نشده است."
            )
            return

        lines = [
            "🏆 **رتبه‌بندی نمایندگان**",
            "",
            "👥 بر اساس تعداد کاربران ثبت‌شده در ربات:",
            "",
        ]
        medals = ("🥇", "🥈", "🥉")
        for index, row in enumerate(rows):
            username = row["username"]
            display = (
                f"@{username}"
                if username
                else (row["brand"] or f"Bot {row['bot_id']}")
            )
            lines.append(
                f"{medals[index]} {display} — 👥 {row['user_count']:,} کاربر"
            )

        await event.respond("\n".join(lines))

    client.add_event_handler(
        group_message,
        events.NewMessage(incoming=True),
    )

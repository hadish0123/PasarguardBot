from __future__ import annotations

from sqlalchemy import func, select
from app.db.models import SupportMessage, SupportTicket
from app.db.session import SessionFactory
from app.runtime.context import require_tenant


class SupportService:
    async def create_ticket(self, user_id: int, subject: str, message: str) -> SupportTicket:
        tenant_id = require_tenant()
        subject = subject.strip()[:160]
        message = message.strip()[:4000]
        if not subject:
            raise ValueError("موضوع تیکت الزامی است.")
        if not message:
            raise ValueError("متن پیام الزامی است.")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            ticket = SupportTicket(tenant_id=tenant_id, telegram_user_id=user_id, subject=subject, status="open")
            session.add(ticket)
            await session.flush()
            session.add(SupportMessage(ticket_id=ticket.id, tenant_id=tenant_id, sender_id=user_id, sender_role="user", body=message))
            await session.commit()
            await session.refresh(ticket)
            return ticket

    async def list_user(self, user_id: int, limit: int = 20) -> list[SupportTicket]:
        tenant_id = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return list((await session.execute(select(SupportTicket).where(SupportTicket.tenant_id == tenant_id, SupportTicket.telegram_user_id == user_id).order_by(SupportTicket.id.desc()).limit(min(max(limit, 1), 50)))).scalars().all())

    async def list_admin(self, status: str | None = None, limit: int = 20, offset: int = 0) -> tuple[list[SupportTicket], bool]:
        tenant_id = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            q = select(SupportTicket).where(SupportTicket.tenant_id == tenant_id)
            if status in {"open", "in_progress", "resolved", "closed"}:
                q = q.where(SupportTicket.status == status)
            rows = list((await session.execute(q.order_by(SupportTicket.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 50) + 1))).scalars().all())
            return rows[:limit], len(rows) > limit

    async def get(self, ticket_id: int) -> SupportTicket | None:
        tenant_id = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.tenant_id == tenant_id))

    async def messages(self, ticket_id: int) -> list[SupportMessage]:
        tenant_id = require_tenant()
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return list((await session.execute(select(SupportMessage).where(SupportMessage.ticket_id == ticket_id, SupportMessage.tenant_id == tenant_id).order_by(SupportMessage.id.asc()))).scalars().all())

    async def add_message(self, ticket_id: int, sender_id: int, sender_role: str, body: str) -> SupportMessage:
        tenant_id = require_tenant()
        body = body.strip()[:4000]
        if not body:
            raise ValueError("متن پیام الزامی است.")
        if sender_role not in {"user", "admin"}:
            raise ValueError("نقش فرستنده نامعتبر است.")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            ticket = await session.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.tenant_id == tenant_id))
            if ticket is None:
                raise LookupError("تیکت پیدا نشد.")
            if ticket.status == "closed":
                raise ValueError("این تیکت بسته شده است.")
            row = SupportMessage(ticket_id=ticket_id, tenant_id=tenant_id, sender_id=sender_id, sender_role=sender_role, body=body)
            session.add(row)
            ticket.status = "in_progress" if sender_role == "admin" else "open"
            await session.commit()
            await session.refresh(row)
            return row

    async def set_status(self, ticket_id: int, status: str) -> SupportTicket:
        tenant_id = require_tenant()
        if status not in {"open", "in_progress", "resolved", "closed"}:
            raise ValueError("وضعیت نامعتبر است.")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            ticket = await session.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.tenant_id == tenant_id))
            if ticket is None:
                raise LookupError("تیکت پیدا نشد.")
            ticket.status = status
            await session.commit()
            await session.refresh(ticket)
            return ticket


SERVICE = SupportService()

from __future__ import annotations
from sqlalchemy import text
from app.db.session import SessionFactory
from app.runtime.context import require_tenant

STATUS = {"open", "in_progress", "resolved", "closed"}

class SupportService:
    async def create_ticket(self, user_id: int, subject: str, message: str):
        tenant = require_tenant(); subject = subject.strip()[:160]; message = message.strip()[:4000]
        if not subject: raise ValueError("موضوع تیکت الزامی است.")
        if not message: raise ValueError("متن پیام الزامی است.")
        if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            ticket = (await session.execute(text("INSERT INTO representative_support_tickets (tenant_id,telegram_user_id,subject,status) VALUES (:t,:u,:s,'open') RETURNING *"), {"t":tenant,"u":user_id,"s":subject})).mappings().one()
            await session.execute(text("INSERT INTO representative_support_messages (ticket_id,tenant_id,sender_id,sender_role,body) VALUES (:id,:t,:u,'user',:b)"), {"id":ticket["id"],"t":tenant,"u":user_id,"b":message})
            await session.commit(); return ticket
    async def list_user(self, user_id: int, limit: int = 20):
        if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return list((await session.execute(text("SELECT * FROM representative_support_tickets WHERE tenant_id=:t AND telegram_user_id=:u ORDER BY id DESC LIMIT :n"), {"t":require_tenant(),"u":user_id,"n":min(max(limit,1),50)})).mappings().all())
    async def list_admin(self, status: str|None=None, limit: int=12, offset: int=0):
        if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            params={"t":require_tenant(),"n":min(max(limit,1),50)+1,"o":max(offset,0)}; where="tenant_id=:t"
            if status in STATUS: where += " AND status=:s"; params["s"]=status
            rows=list((await session.execute(text(f"SELECT * FROM representative_support_tickets WHERE {where} ORDER BY id DESC OFFSET :o LIMIT :n"),params)).mappings().all())
            return rows[:limit], len(rows)>limit
    async def get(self, ticket_id: int):
        if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return (await session.execute(text("SELECT * FROM representative_support_tickets WHERE id=:id AND tenant_id=:t"), {"id":ticket_id,"t":require_tenant()})).mappings().first()
    async def messages(self, ticket_id: int):
        if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return list((await session.execute(text("SELECT * FROM representative_support_messages WHERE ticket_id=:id AND tenant_id=:t ORDER BY id ASC"), {"id":ticket_id,"t":require_tenant()})).mappings().all())
    async def add_message(self, ticket_id: int, sender_id: int, sender_role: str, body: str):
        if sender_role not in {"user","admin"}: raise ValueError("نقش فرستنده نامعتبر است.")
        body=body.strip()[:4000]
        if not body: raise ValueError("متن پیام الزامی است.")
        if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            t=require_tenant(); ticket=(await session.execute(text("SELECT * FROM representative_support_tickets WHERE id=:id AND tenant_id=:t"), {"id":ticket_id,"t":t})).mappings().first()
            if not ticket: raise LookupError("تیکت پیدا نشد.")
            if ticket["status"]=="closed": raise ValueError("این تیکت بسته شده است.")
            await session.execute(text("INSERT INTO representative_support_messages (ticket_id,tenant_id,sender_id,sender_role,body) VALUES (:id,:t,:u,:r,:b)"), {"id":ticket_id,"t":t,"u":sender_id,"r":sender_role,"b":body})
            new_status="in_progress" if sender_role=="admin" else "open"
            await session.execute(text("UPDATE representative_support_tickets SET status=:s,updated_at=now() WHERE id=:id AND tenant_id=:t"), {"s":new_status,"id":ticket_id,"t":t})
            await session.commit(); return await self.get(ticket_id)
    async def set_status(self, ticket_id: int, status: str):
        if status not in STATUS: raise ValueError("وضعیت نامعتبر است.")
        if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            row=(await session.execute(text("UPDATE representative_support_tickets SET status=:s,updated_at=now() WHERE id=:id AND tenant_id=:t RETURNING *"), {"s":status,"id":ticket_id,"t":require_tenant()})).mappings().first()
            if not row: raise LookupError("تیکت پیدا نشد.")
            await session.commit(); return row
SERVICE=SupportService()

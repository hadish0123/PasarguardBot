from __future__ import annotations

from collections.abc import AsyncIterator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings
from app.db.models import Base
engine = create_async_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) if engine else None
async def session_scope() -> AsyncIterator[AsyncSession]:
    if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
    async with SessionFactory() as session: yield session
async def initialize_database() -> None:
    if engine is None: raise RuntimeError("DATABASE_URL is not configured")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("ALTER TABLE representative_plans ADD COLUMN IF NOT EXISTS provider_template_id INTEGER"))
        await connection.execute(text("ALTER TABLE representative_service_subscriptions ADD COLUMN IF NOT EXISTS subscription_url TEXT"))
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_representative_plans_provider_template_id ON representative_plans (provider_template_id)"))
        await connection.execute(text("CREATE TABLE IF NOT EXISTS representative_support_tickets (id SERIAL PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL, telegram_user_id BIGINT NOT NULL, subject VARCHAR(160) NOT NULL, status VARCHAR(24) NOT NULL DEFAULT 'open', created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"))
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_support_tickets_tenant ON representative_support_tickets (tenant_id)"))
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_support_tickets_user ON representative_support_tickets (telegram_user_id)"))
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_support_tickets_status ON representative_support_tickets (status)"))
        await connection.execute(text("CREATE TABLE IF NOT EXISTS representative_support_messages (id SERIAL PRIMARY KEY, ticket_id INTEGER NOT NULL, tenant_id VARCHAR(64) NOT NULL, sender_id BIGINT NOT NULL, sender_role VARCHAR(16) NOT NULL, body TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())"))
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_support_messages_ticket ON representative_support_messages (ticket_id)"))
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_support_messages_tenant ON representative_support_messages (tenant_id)"))

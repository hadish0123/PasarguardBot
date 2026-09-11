from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models import Base


engine = create_async_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) if engine else None


async def session_scope() -> AsyncIterator[AsyncSession]:
    if SessionFactory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with SessionFactory() as session:
        yield session


async def initialize_database() -> None:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        # create_all() intentionally does not alter existing tables. These additive
        # columns keep existing representative databases compatible with the v2 model.
        await connection.execute(text("ALTER TABLE representative_plans ADD COLUMN IF NOT EXISTS provider_template_id INTEGER"))
        await connection.execute(text("ALTER TABLE representative_service_subscriptions ADD COLUMN IF NOT EXISTS subscription_url TEXT"))
        await connection.execute(text("CREATE INDEX IF NOT EXISTS ix_representative_plans_provider_template_id ON representative_plans (provider_template_id)"))

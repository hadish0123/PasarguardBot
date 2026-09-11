from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


engine = create_async_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False) if engine else None


async def session_scope():
    if SessionFactory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    async with SessionFactory() as session:
        yield session

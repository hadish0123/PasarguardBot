from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models import Base


engine = create_async_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
SessionFactory = (
    async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    if engine
    else None
)

# Backwards-compatible session factory used by the representative services.
# Keep a single canonical factory so all DB access shares the same engine.
AsyncSessionLocal = SessionFactory


async def session_scope() -> AsyncIterator[AsyncSession]:
    if SessionFactory is None:
        raise RuntimeError("SQLALCHEMY_DATABASE_URL is not configured")
    async with SessionFactory() as session:
        yield session


async def initialize_database() -> None:
    if engine is None:
        raise RuntimeError("SQLALCHEMY_DATABASE_URL is not configured")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

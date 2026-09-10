from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from config import (
    SQLALCHEMY_DATABASE_URL,
    SQLALCHEMY_MAX_OVERFLOW,
    SQLALCHEMY_POOL_SIZE,
    SQLALCHEMY_POOL_TIMEOUT,
)

Base = declarative_base()


def _make_engine(url: str):
    if url.startswith("sqlite"):
        return create_async_engine(url, connect_args={"check_same_thread": False})
    return create_async_engine(
        url,
        pool_size=SQLALCHEMY_POOL_SIZE,
        max_overflow=SQLALCHEMY_MAX_OVERFLOW,
        pool_recycle=300,
        pool_timeout=SQLALCHEMY_POOL_TIMEOUT,
        pool_pre_ping=True,
    )


engine = _make_engine(SQLALCHEMY_DATABASE_URL)
CentralSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)

_tenant_engines: dict[str, object] = {}
_tenant_sessions: dict[str, async_sessionmaker[AsyncSession]] = {}


def _tenant_session_factory(database_url: str):
    factory = _tenant_sessions.get(database_url)
    if factory is None:
        tenant_engine = _make_engine(database_url)
        _tenant_engines[database_url] = tenant_engine
        factory = async_sessionmaker(
            autocommit=False, autoflush=False, bind=tenant_engine, expire_on_commit=False
        )
        _tenant_sessions[database_url] = factory
    return factory


class _RoutedSessionFactory:
    """Drop-in async_sessionmaker facade routed by the current tenant."""

    def __call__(self, *args, **kwargs):
        from app.runtime.context import get_current_tenant

        tenant = get_current_tenant()
        if tenant is None:
            return CentralSessionLocal(*args, **kwargs)
        return _tenant_session_factory(tenant.database_url)(*args, **kwargs)

    def central(self, *args, **kwargs):
        return CentralSessionLocal(*args, **kwargs)


AsyncSessionLocal = _RoutedSessionFactory()

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    DATABASE_DIALECT = "sqlite"
elif SQLALCHEMY_DATABASE_URL.startswith("postgresql"):
    DATABASE_DIALECT = "postgresql"
elif SQLALCHEMY_DATABASE_URL.startswith("mysql"):
    DATABASE_DIALECT = "mysql"
else:
    raise ValueError("Unsupported database URL")


class GetDB:
    def __init__(self):
        self.db = AsyncSessionLocal()

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_value is not None:
            await self.db.rollback()
        await self.db.close()


async def get_db():
    async with GetDB() as db:
        yield db


async def dispose_tenant_engines() -> None:
    for tenant_engine in list(_tenant_engines.values()):
        await tenant_engine.dispose()
    _tenant_engines.clear()
    _tenant_sessions.clear()

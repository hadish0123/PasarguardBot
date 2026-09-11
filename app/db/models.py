from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RegistrationStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"
    REJECTED = "rejected"


class RegistrationStep(StrEnum):
    BRAND = "brand"
    BOT_TOKEN = "bot_token"
    BOT_ID = "bot_id"
    PANEL_URL = "panel_url"
    PANEL_USERNAME = "panel_username"
    PANEL_API_KEY = "panel_api_key"
    REVIEW = "review"
    COMPLETE = "complete"


class TenantStatus(StrEnum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    FAILED = "failed"


class RepresentativeRegistration(Base):
    __tablename__ = "representative_registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tracking_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bot_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bot_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    panel_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    panel_username: Mapped[str | None] = mapped_column(String(190), nullable=True)
    panel_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    step: Mapped[str] = mapped_column(String(24), default=RegistrationStep.BRAND.value)
    status: Mapped[str] = mapped_column(String(24), default=RegistrationStatus.DRAFT.value, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TenantRecord(Base):
    __tablename__ = "representative_tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    registration_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    brand: Mapped[str] = mapped_column(String(120))
    bot_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    bot_username: Mapped[str | None] = mapped_column(String(190), nullable=True)
    bot_token_encrypted: Mapped[str] = mapped_column(Text)
    panel_url: Mapped[str] = mapped_column(Text)
    panel_username: Mapped[str | None] = mapped_column(String(190), nullable=True)
    panel_api_key_encrypted: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default=TenantStatus.PROVISIONING.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Plan(Base):
    __tablename__ = "representative_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(120))
    volume_gb: Mapped[float] = mapped_column(Float)
    days: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

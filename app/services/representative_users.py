from __future__ import annotations

from sqlalchemy import or_, select

from app.db.models import RepresentativeUser, UserBalanceLog
from app.db.session import SessionFactory
from app.runtime.context import require_tenant


class RepresentativeUserService:
    def _tenant(self) -> str:
        return require_tenant()

    async def upsert_from_sender(self, sender) -> RepresentativeUser:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        tenant_id = self._tenant()
        async with SessionFactory() as session:
            user = await session.scalar(select(RepresentativeUser).where(
                RepresentativeUser.tenant_id == tenant_id,
                RepresentativeUser.telegram_user_id == int(sender.id),
            ))
            if user is None:
                user = RepresentativeUser(
                    tenant_id=tenant_id,
                    telegram_user_id=int(sender.id),
                    username=getattr(sender, "username", None),
                    first_name=getattr(sender, "first_name", None),
                    last_name=getattr(sender, "last_name", None),
                )
                session.add(user)
            else:
                user.username = getattr(sender, "username", None)
                user.first_name = getattr(sender, "first_name", None)
                user.last_name = getattr(sender, "last_name", None)
            await session.commit()
            await session.refresh(user)
            return user

    async def list(self, query: str | None = None, limit: int = 12) -> list[RepresentativeUser]:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        tenant_id = self._tenant()
        async with SessionFactory() as session:
            stmt = select(RepresentativeUser).where(RepresentativeUser.tenant_id == tenant_id)
            if query:
                q = query.strip().lstrip("@").lower()
                try:
                    numeric_id = int(q)
                except ValueError:
                    numeric_id = None
                terms = [RepresentativeUser.username.ilike(f"%{q}%"), RepresentativeUser.first_name.ilike(f"%{q}%"), RepresentativeUser.last_name.ilike(f"%{q}%")]
                if numeric_id is not None:
                    terms.append(RepresentativeUser.telegram_user_id == numeric_id)
                stmt = stmt.where(or_(*terms))
            result = await session.execute(stmt.order_by(RepresentativeUser.id.desc()).limit(max(1, min(limit, 50))))
            return list(result.scalars().all())

    async def get(self, user_id: int) -> RepresentativeUser | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.scalar(select(RepresentativeUser).where(
                RepresentativeUser.id == user_id,
                RepresentativeUser.tenant_id == self._tenant(),
            ))

    async def get_by_telegram_id(self, telegram_user_id: int) -> RepresentativeUser | None:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.scalar(select(RepresentativeUser).where(
                RepresentativeUser.telegram_user_id == telegram_user_id,
                RepresentativeUser.tenant_id == self._tenant(),
            ))

    async def toggle_block(self, user_id: int) -> RepresentativeUser:
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            user = await session.scalar(select(RepresentativeUser).where(
                RepresentativeUser.id == user_id,
                RepresentativeUser.tenant_id == self._tenant(),
            ))
            if user is None:
                raise LookupError("user not found")
            user.blocked = not user.blocked
            await session.commit()
            await session.refresh(user)
            return user

    async def adjust_balance(self, user_id: int, amount: float, reason: str, actor_id: int) -> RepresentativeUser:
        if amount == 0:
            raise ValueError("amount cannot be zero")
        if not reason.strip():
            raise ValueError("reason is required")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        tenant_id = self._tenant()
        async with SessionFactory() as session:
            user = await session.scalar(select(RepresentativeUser).where(
                RepresentativeUser.id == user_id,
                RepresentativeUser.tenant_id == tenant_id,
            ))
            if user is None:
                raise LookupError("user not found")
            new_balance = user.balance + amount
            if new_balance < 0:
                raise ValueError("balance cannot become negative")
            user.balance = new_balance
            session.add(UserBalanceLog(tenant_id=tenant_id, user_id=user.id, actor_id=actor_id, amount=amount, reason=reason.strip()[:500]))
            await session.commit()
            await session.refresh(user)
            return user

    async def is_blocked(self, telegram_user_id: int) -> bool:
        user = await self.get_by_telegram_id(telegram_user_id)
        return bool(user and user.blocked)


SERVICE = RepresentativeUserService()

from __future__ import annotations

from sqlalchemy import select

from app.db.models import RepresentativeLink
from app.db.session import SessionFactory
from app.runtime.context import require_tenant


class LinkService:
    async def list(self, kind: str | None = None):
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            query = select(RepresentativeLink).where(RepresentativeLink.tenant_id == require_tenant())
            if kind:
                query = query.where(RepresentativeLink.kind == kind)
            result = await session.execute(query.order_by(RepresentativeLink.id.desc()))
            return list(result.scalars().all())

    async def create(self, title: str, url: str, kind: str = "general"):
        title = title.strip()
        url = url.strip()
        kind = kind.strip() or "general"
        if not title or len(title) > 120:
            raise ValueError("عنوان لینک نامعتبر است.")
        if not (url.startswith("https://") or url.startswith("http://")):
            raise ValueError("لینک باید با http:// یا https:// شروع شود.")
        if len(url) > 1000:
            raise ValueError("لینک بیش از حد طولانی است.")
        if len(kind) > 40:
            raise ValueError("نوع لینک نامعتبر است.")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            row = RepresentativeLink(
                tenant_id=require_tenant(), title=title, url=url, kind=kind,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def get(self, link_id: int):
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            return await session.scalar(
                select(RepresentativeLink).where(
                    RepresentativeLink.id == link_id,
                    RepresentativeLink.tenant_id == require_tenant(),
                )
            )

    async def update(self, link_id: int, title: str, url: str, kind: str = "general"):
        title = title.strip()
        url = url.strip()
        kind = kind.strip() or "general"
        if not title or len(title) > 120:
            raise ValueError("عنوان لینک نامعتبر است.")
        if not (url.startswith("https://") or url.startswith("http://")):
            raise ValueError("لینک باید با http:// یا https:// شروع شود.")
        if len(url) > 1000 or len(kind) > 40:
            raise ValueError("اطلاعات لینک بیش از حد مجاز است.")
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            row = await session.scalar(
                select(RepresentativeLink).where(
                    RepresentativeLink.id == link_id,
                    RepresentativeLink.tenant_id == require_tenant(),
                )
            )
            if row is None:
                raise LookupError("لینک پیدا نشد.")
            row.title, row.url, row.kind = title, url, kind
            await session.commit()
            await session.refresh(row)
            return row

    async def delete(self, link_id: int):
        if SessionFactory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        async with SessionFactory() as session:
            row = await session.scalar(
                select(RepresentativeLink).where(
                    RepresentativeLink.id == link_id,
                    RepresentativeLink.tenant_id == require_tenant(),
                )
            )
            if row is None:
                raise LookupError("لینک پیدا نشد.")
            await session.delete(row)
            await session.commit()


SERVICE = LinkService()

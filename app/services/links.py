from __future__ import annotations
from sqlalchemy import select
from app.db.models import RepresentativeLink
from app.db.session import SessionFactory
from app.runtime.context import require_tenant
class LinkService:
 async def list(self):
  if SessionFactory is None:raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as s:return list((await s.execute(select(RepresentativeLink).where(RepresentativeLink.tenant_id==require_tenant()).order_by(RepresentativeLink.id.desc()))).scalars().all())
 async def create(self,title,url,kind="general"):
  title=title.strip(); url=url.strip()
  if not title or len(title)>120:raise ValueError("عنوان لینک نامعتبر است.")
  if not (url.startswith("https://") or url.startswith("http://")):raise ValueError("لینک باید با http:// یا https:// شروع شود.")
  if len(url)>1000:raise ValueError("لینک بیش از حد طولانی است.")
  if SessionFactory is None:raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as s:
   row=RepresentativeLink(tenant_id=require_tenant(),title=title,url=url,kind=kind[:40]); s.add(row); await s.commit(); await s.refresh(row); return row
 async def delete(self,link_id):
  if SessionFactory is None:raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as s:
   row=await s.scalar(select(RepresentativeLink).where(RepresentativeLink.id==link_id,RepresentativeLink.tenant_id==require_tenant()))
   if row is None:raise LookupError("link not found")
   await s.delete(row); await s.commit()
SERVICE=LinkService()

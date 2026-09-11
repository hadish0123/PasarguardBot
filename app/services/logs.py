from __future__ import annotations
from sqlalchemy import select
from app.db.models import RepresentativeLog
from app.db.session import SessionFactory
from app.runtime.context import require_tenant
class LogService:
 async def add(self,action:str,details:str="",actor_id:int|None=None):
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:
   row=RepresentativeLog(tenant_id=require_tenant(),actor_id=actor_id,action=action[:120],details=details[:1000]); session.add(row); await session.commit(); return row
 async def list(self,limit=30):
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:
   return list((await session.execute(select(RepresentativeLog).where(RepresentativeLog.tenant_id==require_tenant()).order_by(RepresentativeLog.id.desc()).limit(limit))).scalars().all())
SERVICE=LogService()

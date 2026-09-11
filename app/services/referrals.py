from __future__ import annotations
from sqlalchemy import func, select
from app.db.models import Referral, RepresentativeUser
from app.db.session import AsyncSessionLocal
from app.runtime.context import require_tenant
class ReferralService:
 async def stats(self, telegram_user_id:int):
  tenant_id=require_tenant()
  async with AsyncSessionLocal() as db:
   user=await db.scalar(select(RepresentativeUser).where(RepresentativeUser.tenant_id==tenant_id,RepresentativeUser.telegram_user_id==telegram_user_id))
   if user is None: return 0
   count=await db.scalar(select(func.count()).select_from(Referral).where(Referral.tenant_id==tenant_id,Referral.inviter_user_id==user.id))
   return int(count or 0)
 async def attach(self, inviter_telegram_id:int, referred_telegram_id:int):
  tenant_id=require_tenant()
  if inviter_telegram_id==referred_telegram_id: raise ValueError("نمی‌توانید خودتان را دعوت کنید.")
  async with AsyncSessionLocal() as db:
   inviter=await db.scalar(select(RepresentativeUser).where(RepresentativeUser.tenant_id==tenant_id,RepresentativeUser.telegram_user_id==inviter_telegram_id))
   referred=await db.scalar(select(RepresentativeUser).where(RepresentativeUser.tenant_id==tenant_id,RepresentativeUser.telegram_user_id==referred_telegram_id))
   if not inviter or not referred: raise LookupError("کاربر پیدا نشد.")
   old=await db.scalar(select(Referral).where(Referral.tenant_id==tenant_id,Referral.referred_user_id==referred.id))
   if old: return old
   row=Referral(tenant_id=tenant_id,inviter_user_id=inviter.id,referred_user_id=referred.id); db.add(row); await db.commit(); await db.refresh(row); return row
SERVICE=ReferralService()

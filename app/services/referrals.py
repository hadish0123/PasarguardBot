from __future__ import annotations
from sqlalchemy import func, select
from app.db.models import Referral, ReferralReward, RepresentativeUser, UserBalanceLog
from app.db.session import AsyncSessionLocal
from app.runtime.context import require_tenant
from app.services.representative_settings import SERVICE as SETTINGS
class ReferralService:
 async def stats(self, telegram_user_id:int):
  tenant_id=require_tenant()
  async with AsyncSessionLocal() as db:
   user=await db.scalar(select(RepresentativeUser).where(RepresentativeUser.tenant_id==tenant_id,RepresentativeUser.telegram_user_id==telegram_user_id))
   if user is None:return 0
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
   if old:return old
   row=Referral(tenant_id=tenant_id,inviter_user_id=inviter.id,referred_user_id=referred.id); db.add(row); await db.flush()
   settings=await SETTINGS.snapshot(); mode=settings.get("referral_reward_mode","none")
   if mode=="fixed":
    amount=float(settings.get("referral_reward_value","0") or 0)
    if amount>0:
     inviter.balance=float(inviter.balance)+amount
     db.add(UserBalanceLog(tenant_id=tenant_id,user_id=inviter.id,actor_id=referred_telegram_id,amount=amount,reason=f"پاداش ورود دعوت‌شده #{referred.id}"))
     db.add(ReferralReward(tenant_id=tenant_id,referral_id=row.id,order_id=None,inviter_user_id=inviter.id,amount=amount,reason="fixed referral signup reward"))
   await db.commit(); await db.refresh(row); return row
 async def reward_paid_order(self, order_id:int, buyer_telegram_id:int, amount:float):
  tenant_id=require_tenant(); settings=await SETTINGS.snapshot(); mode=settings.get("referral_reward_mode","none")
  if mode!="percent" or float(amount)<=0:return 0.0
  percent=float(settings.get("referral_reward_value","0") or 0); reward=round(float(amount)*percent/100,2)
  if reward<=0:return 0.0
  async with AsyncSessionLocal() as db:
   referral=await db.scalar(select(Referral).join(RepresentativeUser,Referral.referred_user_id==RepresentativeUser.id).where(Referral.tenant_id==tenant_id,RepresentativeUser.telegram_user_id==buyer_telegram_id))
   if referral is None:return 0.0
   existing=await db.scalar(select(ReferralReward).where(ReferralReward.tenant_id==tenant_id,ReferralReward.order_id==order_id))
   if existing:return float(existing.amount)
   inviter=await db.scalar(select(RepresentativeUser).where(RepresentativeUser.id==referral.inviter_user_id,RepresentativeUser.tenant_id==tenant_id).with_for_update())
   if inviter is None:return 0.0
   inviter.balance=float(inviter.balance)+reward
   db.add(UserBalanceLog(tenant_id=tenant_id,user_id=inviter.id,actor_id=buyer_telegram_id,amount=reward,reason=f"کمیسیون دعوت سفارش #{order_id}"))
   db.add(ReferralReward(tenant_id=tenant_id,referral_id=referral.id,order_id=order_id,inviter_user_id=inviter.id,amount=reward,reason=f"{percent:g}% order referral commission"))
   await db.commit()
  return reward
SERVICE=ReferralService()

from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.models import CheckoutRecord, Discount, DiscountRedemption, Order, Plan, RepresentativeUser, UserBalanceLog
from app.db.session import SessionFactory
from app.runtime.context import require_tenant
from app.services.logs import SERVICE as LOG_SERVICE

def _toman(value: float) -> float: return float(round(float(value)))
class OrderService:
 async def list(self,status=None,limit=30):
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:
   stmt=select(Order).where(Order.tenant_id==require_tenant()).order_by(Order.id.desc()).limit(limit)
   if status: stmt=stmt.where(Order.status==status)
   return list((await session.execute(stmt)).scalars().all())
 async def get(self,order_id):
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:return await session.scalar(select(Order).where(Order.id==order_id,Order.tenant_id==require_tenant()))
 async def checkout(self,telegram_user_id,plan_id,discount_code=None):
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  tenant_id=require_tenant()
  async with SessionFactory() as session:
   plan=await session.scalar(select(Plan).where(Plan.id==plan_id,Plan.tenant_id==tenant_id,Plan.enabled.is_(True)))
   if plan is None: raise LookupError("plan not found or disabled")
   subtotal=_toman(plan.price); discount_amount=0.0; discount=None; code=None
   if discount_code:
    code=discount_code.strip().upper(); discount=await session.scalar(select(Discount).where(Discount.tenant_id==tenant_id,Discount.code==code).with_for_update())
    if discount is None: raise LookupError("کد تخفیف پیدا نشد.")
    if not discount.enabled: raise ValueError("این کد تخفیف غیرفعال است.")
    if discount.expires_at and discount.expires_at<=datetime.now(timezone.utc): raise ValueError("اعتبار این کد تخفیف به پایان رسیده است.")
    if discount.max_uses is not None and discount.used_count>=discount.max_uses: raise ValueError("ظرفیت استفاده از این کد تکمیل شده است.")
    discount_amount=_toman(subtotal*float(discount.percent)/100)
   total=max(0.0,_toman(subtotal-discount_amount)); order=Order(tenant_id=tenant_id,telegram_user_id=telegram_user_id,plan_id=plan.id,plan_name=plan.name,volume_gb=plan.volume_gb,days=plan.days,amount=total,status="pending")
   session.add(order); await session.flush(); session.add(CheckoutRecord(tenant_id=tenant_id,order_id=order.id,telegram_user_id=telegram_user_id,subtotal=subtotal,discount_amount=discount_amount,total=total,discount_code=code))
   if discount:
    discount.used_count+=1; session.add(DiscountRedemption(tenant_id=tenant_id,discount_id=discount.id,order_id=order.id,telegram_user_id=telegram_user_id,amount=discount_amount))
   await session.commit(); await session.refresh(order)
  await LOG_SERVICE.add("order.checkout",f"order=#{order.id} subtotal={subtotal} discount={discount_amount} total={total} currency=TOMAN code={code or '-'}",telegram_user_id); return order
 async def create_wallet_topup(self,telegram_user_id:int,amount:float):
  amount=_toman(amount)
  if amount<5000 or amount>100_000_000: raise ValueError("مبلغ شارژ باید بین ۵,۰۰۰ تا ۱۰۰,۰۰۰,۰۰۰ تومان باشد.")
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  tenant_id=require_tenant()
  async with SessionFactory() as session:
   order=Order(tenant_id=tenant_id,telegram_user_id=telegram_user_id,plan_id=0,plan_name="شارژ کیف پول",volume_gb=0,days=0,amount=amount,status="pending"); session.add(order); await session.flush(); session.add(CheckoutRecord(tenant_id=tenant_id,order_id=order.id,telegram_user_id=telegram_user_id,subtotal=amount,discount_amount=0,total=amount,discount_code=None)); await session.commit(); await session.refresh(order)
  await LOG_SERVICE.add("wallet.topup_created",f"order=#{order.id} amount={amount} currency=TOMAN",telegram_user_id); return order
 async def checkout_record(self,order_id):
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:return await session.scalar(select(CheckoutRecord).where(CheckoutRecord.tenant_id==require_tenant(),CheckoutRecord.order_id==order_id))
 async def submit_payment(self,order_id,reference):
  reference=reference.strip()
  if not reference or len(reference)>190: raise ValueError("شناسه پرداخت نامعتبر است.")
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:
   order=await session.scalar(select(Order).where(Order.id==order_id,Order.tenant_id==require_tenant()).with_for_update())
   if order is None: raise LookupError("سفارش پیدا نشد.")
   if order.status!="pending": raise ValueError("این سفارش دیگر قابل پرداخت نیست.")
   record=await session.scalar(select(CheckoutRecord).where(CheckoutRecord.tenant_id==order.tenant_id,CheckoutRecord.order_id==order.id))
   if record is None: raise LookupError("جزئیات پرداخت سفارش پیدا نشد.")
   record.payment_reference=reference; record.payment_submitted_at=datetime.now(timezone.utc); await session.commit(); await session.refresh(order)
  await LOG_SERVICE.add("order.payment_submitted",f"order=#{order_id}",order.telegram_user_id); return order
 async def set_status(self,order_id,status):
  if status not in {"pending","paid","fulfilled","cancelled"}: raise ValueError("invalid order status")
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  tenant_id=require_tenant(); provision_after=False; revoke_after=False; wallet_credit=0.0; wallet_user=0
  async with SessionFactory() as session:
   # Serialize status transitions for the same order. This prevents the
   # MySQL/InnoDB "Record has changed since last read" race seen when two
   # admin callbacks try to update the same order concurrently.
   order=await session.scalar(select(Order).where(Order.id==order_id,Order.tenant_id==tenant_id).with_for_update())
   if order is None: raise LookupError("order not found")
   record=await session.scalar(select(CheckoutRecord).where(CheckoutRecord.tenant_id==tenant_id,CheckoutRecord.order_id==order.id)); redemption=await session.scalar(select(DiscountRedemption).where(DiscountRedemption.tenant_id==tenant_id,DiscountRedemption.order_id==order.id)); old=order.status
   if old==status:return order
   allowed={"pending":{"paid","cancelled"},"paid":{"fulfilled","cancelled"},"fulfilled":set(),"cancelled":set()}
   if status not in allowed.get(old,set()): raise ValueError(f"انتقال وضعیت {old} به {status} مجاز نیست.")
   if status=="paid" and order.amount>0 and (record is None or not record.payment_reference): raise ValueError("برای تأیید پرداخت، ابتدا رسید/شناسه پرداخت کاربر باید ثبت شده باشد.")
   if status=="fulfilled":
    from app.db.models import ServiceSubscription
    subscription=await session.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id==tenant_id,ServiceSubscription.order_id==order.id))
    if subscription is None or subscription.status!="active": raise ValueError("سفارش تا فعال شدن سرویس پاسارگارد قابل تکمیل نیست.")
   if status=="cancelled":
    from app.db.models import ServiceSubscription
    subscription=await session.scalar(select(ServiceSubscription).where(ServiceSubscription.tenant_id==tenant_id,ServiceSubscription.order_id==order.id))
    if subscription and subscription.status=="active": raise ValueError("سرویس فعال است؛ ابتدا سرویس را لغو/ابطال کنید.")
    revoke_after=subscription is not None
    if redemption is not None:
     discount=await session.scalar(select(Discount).where(Discount.tenant_id==tenant_id,Discount.id==redemption.discount_id).with_for_update())
     if discount is not None and discount.used_count>0: discount.used_count-=1
     await session.delete(redemption)
   order.status=status
   if status=="paid" and order.plan_id==0:
    user=await session.scalar(select(RepresentativeUser).where(RepresentativeUser.tenant_id==tenant_id,RepresentativeUser.telegram_user_id==order.telegram_user_id).with_for_update())
    if user is None: raise LookupError("کاربر کیف پول پیدا نشد.")
    user.balance=float(user.balance)+float(order.amount); session.add(UserBalanceLog(tenant_id=tenant_id,user_id=user.id,actor_id=order.telegram_user_id,amount=float(order.amount),reason=f"شارژ کیف پول بابت سفارش #{order.id}")); wallet_credit=float(order.amount); wallet_user=order.telegram_user_id
   await session.commit(); await session.refresh(order); provision_after=status=="paid" and order.plan_id!=0
  if wallet_credit: await LOG_SERVICE.add("wallet.topup_approved",f"order=#{order_id} user={wallet_user} amount={wallet_credit} currency=TOMAN")
  if revoke_after: await LOG_SERVICE.add("order.cancelled",f"order=#{order_id} reservation released")
  if provision_after:
   try:
    from app.services.pasarguard_provisioning import PasarguardProvisioningService
    subscription=await PasarguardProvisioningService().provision_paid_order(order.id); await LOG_SERVICE.add("order.provisioned",f"order=#{order.id} provider_id={subscription.provider_service_id or '-'}")
   except ValueError as exc: await LOG_SERVICE.add("order.provisioning_pending",f"order=#{order.id} reason={exc}")
   except Exception as exc: await LOG_SERVICE.add("order.provisioning_failed",f"order=#{order.id} error={exc}")
   try:
    from app.services.referrals import SERVICE as REFERRAL_SERVICE
    reward=await REFERRAL_SERVICE.reward_paid_order(order.id,order.telegram_user_id,order.amount)
    if reward: await LOG_SERVICE.add("referral.reward",f"order=#{order.id} amount={reward} currency=TOMAN")
   except Exception as exc: await LOG_SERVICE.add("referral.reward_failed",f"order=#{order.id} error={exc}")
  await LOG_SERVICE.add("order.status_changed",f"order=#{order_id} {old}->{status}"); return order
SERVICE=OrderService()

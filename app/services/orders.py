from __future__ import annotations
from sqlalchemy import select
from app.db.models import Order,Plan
from app.db.session import SessionFactory
from app.runtime.context import require_tenant
from app.services.logs import SERVICE as LOG_SERVICE
class OrderService:
 async def list(self,status=None,limit=30):
  if SessionFactory is None:raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:
   stmt=select(Order).where(Order.tenant_id==require_tenant()).order_by(Order.id.desc()).limit(limit)
   if status:stmt=stmt.where(Order.status==status)
   return list((await session.execute(stmt)).scalars().all())
 async def get(self,order_id):
  if SessionFactory is None:raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:return await session.scalar(select(Order).where(Order.id==order_id,Order.tenant_id==require_tenant()))
 async def create(self,telegram_user_id,plan_id):
  if SessionFactory is None:raise RuntimeError("DATABASE_URL is not configured")
  tenant_id=require_tenant()
  async with SessionFactory() as session:
   plan=await session.scalar(select(Plan).where(Plan.id==plan_id,Plan.tenant_id==tenant_id,Plan.enabled.is_(True)))
   if plan is None:raise LookupError("plan not found or disabled")
   order=Order(tenant_id=tenant_id,telegram_user_id=telegram_user_id,plan_id=plan.id,plan_name=plan.name,volume_gb=plan.volume_gb,days=plan.days,amount=plan.price,status="pending"); session.add(order); await session.commit(); await session.refresh(order)
  await LOG_SERVICE.add("order.created",f"order=#{order.id} plan={order.plan_name}",telegram_user_id); return order
 async def set_status(self,order_id,status):
  if status not in {"pending","paid","fulfilled","cancelled"}:raise ValueError("invalid order status")
  if SessionFactory is None:raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:
   order=await session.scalar(select(Order).where(Order.id==order_id,Order.tenant_id==require_tenant()))
   if order is None:raise LookupError("order not found")
   old=order.status; order.status=status; await session.commit(); await session.refresh(order)
  await LOG_SERVICE.add("order.status_changed",f"order=#{order_id} {old}->{status}"); return order
SERVICE=OrderService()

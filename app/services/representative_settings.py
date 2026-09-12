from __future__ import annotations
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from app.db.models import RepresentativeSetting
from app.db.session import SessionFactory
from app.runtime.context import require_tenant
DEFAULTS={"brand":"","support_username":"","timezone":"Asia/Tehran","payment_card_number":"","payment_card_holder":"","referral_reward_mode":"none","referral_reward_value":"0","force_join_channel_id":"","trial_enabled":"1","trial_volume_value":"1","trial_volume_unit":"GB","trial_days":"1"}
class RepresentativeSettingsService:
 async def snapshot(self)->dict[str,str]:
  tenant=require_tenant()
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:
   rows=(await session.execute(select(RepresentativeSetting).where(RepresentativeSetting.tenant_id==tenant))).scalars().all()
  values=dict(DEFAULTS)
  for row in rows:
   if row.key in values: values[row.key]=row.value
  return values
 async def set(self,key:str,value:str)->dict[str,str]:
  if key not in DEFAULTS: raise ValueError("تنظیم نامعتبر است.")
  value=value.strip()
  if key=="referral_reward_mode":
   if value not in {"none","fixed","percent"}: raise ValueError("نوع پاداش دعوت نامعتبر است.")
  elif key=="referral_reward_value":
   try: number=float(value)
   except ValueError as exc: raise ValueError("مبلغ/درصد پاداش باید عدد باشد.") from exc
   if number<0: raise ValueError("مبلغ/درصد پاداش نمی‌تواند منفی باشد.")
   mode=(await self.snapshot()).get("referral_reward_mode","none")
   if mode=="percent" and number>100: raise ValueError("درصد پاداش نمی‌تواند بیشتر از ۱۰۰ باشد.")
   value=str(round(number,2))
  elif key=="force_join_channel_id":
   if value:
    try: int(value)
    except ValueError as exc: raise ValueError("آیدی کانال باید عددی باشد؛ مثال: -1001234567890") from exc
  elif key=="trial_enabled":
   if value not in {"0","1"}: raise ValueError("وضعیت سرویس تستی نامعتبر است.")
  elif key=="trial_volume_value":
   try: number=float(value.replace(",","."))
   except ValueError as exc: raise ValueError("حجم سرویس تستی باید عدد باشد.") from exc
   if number<=0 or number>1048576: raise ValueError("حجم سرویس تستی باید بیشتر از صفر و منطقی باشد.")
   value=str(round(number,3))
  elif key=="trial_volume_unit":
   value=value.upper()
   if value not in {"MB","GB"}: raise ValueError("واحد حجم فقط MB یا GB است.")
  elif key=="trial_days":
   try: number=int(value)
   except ValueError as exc: raise ValueError("مدت سرویس تستی باید عدد صحیح باشد.") from exc
   if number<1 or number>3650: raise ValueError("مدت سرویس تستی باید بین ۱ تا ۳۶۵۰ روز باشد.")
   value=str(number)
  elif key=="brand":
   if value and len(value)>120: raise ValueError("نام برند بیش از حد طولانی است.")
  elif key=="support_username":
   value=value.lstrip("@").strip()
   if value and (len(value)>64 or not value.replace("_","").isalnum()): raise ValueError("یوزرنیم پشتیبانی نامعتبر است.")
  elif key=="timezone":
   if len(value)>80: raise ValueError("منطقه زمانی نامعتبر است.")
   try: ZoneInfo(value)
   except ZoneInfoNotFoundError as exc: raise ValueError("منطقه زمانی معتبر نیست؛ مثال: Asia/Tehran") from exc
  elif key=="payment_card_number":
   digits=value.replace("-","").replace(" ","")
   if not digits.isdigit() or len(digits)!=16: raise ValueError("شماره کارت باید ۱۶ رقم باشد.")
   value=digits
  elif key=="payment_card_holder" and len(value)>120: raise ValueError("نام صاحب کارت بیش از حد طولانی است.")
  tenant=require_tenant()
  if SessionFactory is None: raise RuntimeError("DATABASE_URL is not configured")
  async with SessionFactory() as session:
   row=await session.scalar(select(RepresentativeSetting).where(RepresentativeSetting.tenant_id==tenant,RepresentativeSetting.key==key))
   if row is None: session.add(RepresentativeSetting(tenant_id=tenant,key=key,value=value))
   else: row.value=value
   await session.commit()
  return await self.snapshot()
SERVICE=RepresentativeSettingsService()

from __future__ import annotations
from sqlalchemy import select
from app.db.models import RepresentativeText
from app.db.session import session_scope
from app.runtime.context import require_tenant

DEFAULTS={
 "welcome":"🏪 به فروشگاه نمایندگی خوش آمدید.\n\nاز گزینه‌های زیر شروع کنید.",
 "shop_title":"🏪 فروشگاه",
 "shop_hint":"یکی از گزینه‌های زیر را انتخاب کنید.",
 "blocked_user":"🚫 دسترسی شما به این فروشگاه مسدود شده است.\n\nدر صورت اشتباه با پشتیبانی تماس بگیرید.",
 "plans_empty":"🛒 در حال حاضر پلن فعالی برای فروش وجود ندارد.",
 "buy_title":"🛒 انتخاب سرویس",
 "buy_hint":"پلن موردنظر را انتخاب کنید:",
 "support_button":"🆘 پشتیبانی",
 "buy_button":"🛒 خرید سرویس",
 "services_button":"📦 سرویس‌های من",
 "wallet_button":"💳 کیف پول",
 "profile_button":"👤 پروفایل",
 "referral_button":"🎁 دعوت دوستان",
 "discount_button":"🎟 کد تخفیف",
 "trial_button":"🎁 سرویس آزمایشی",
}
LABELS={
 "welcome":"پیام خوش‌آمدگویی","shop_title":"عنوان فروشگاه","shop_hint":"راهنمای فروشگاه","blocked_user":"پیام کاربر مسدود","plans_empty":"پیام نبود پلن","buy_title":"عنوان خرید","buy_hint":"راهنمای خرید","support_button":"دکمه پشتیبانی","buy_button":"دکمه خرید","services_button":"دکمه سرویس‌های من","wallet_button":"دکمه کیف پول","profile_button":"دکمه پروفایل","referral_button":"دکمه دعوت دوستان","discount_button":"دکمه کد تخفیف","trial_button":"دکمه سرویس آزمایشی"
}
class TextService:
 async def all(self):
  tenant=require_tenant()
  async for session in session_scope(): rows=(await session.execute(select(RepresentativeText).where(RepresentativeText.tenant_id==tenant))).scalars().all()
  values=dict(DEFAULTS); values.update({r.key:r.value for r in rows}); return values
 async def get(self,key): return (await self.all()).get(key,DEFAULTS.get(key,""))
 async def set(self,key,value):
  if key not in DEFAULTS: raise ValueError("متن نامعتبر است.")
  value=value.strip()
  if not value: raise ValueError("متن نمی‌تواند خالی باشد.")
  if len(value)>4000: raise ValueError("متن بیش از حد طولانی است.")
  tenant=require_tenant()
  async for session in session_scope():
   row=(await session.execute(select(RepresentativeText).where(RepresentativeText.tenant_id==tenant,RepresentativeText.key==key))).scalar_one_or_none()
   if row is None: session.add(RepresentativeText(tenant_id=tenant,key=key,value=value))
   else: row.value=value
   await session.commit()
  return value
 async def reset(self,key): return await self.set(key,DEFAULTS[key])
SERVICE=TextService()

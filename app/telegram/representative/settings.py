from __future__ import annotations
from telethon import Button, events
from app.core.ids import REP_HOME
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService
from app.services.representative_settings import SERVICE
PREFIX=b"rep:settings:"; INPUTS:dict[tuple[str,int],str]={}
def register(client,tenant_id=None):
 async def cb(event):
  async with tenant_dispatch(tenant_id):
   if not await _auth(event): return await event.answer("دسترسی مدیریت ندارید.",alert=True)
   await handle(event)
 async def msg(event):
  async with tenant_dispatch(tenant_id):
   if not await _auth(event): return
   key=(get_tenant(),event.sender_id); field=INPUTS.get(key)
   if not field:return
   value=(event.raw_text or "").strip()
   if value in {"/cancel","لغو"}:
    INPUTS.pop(key,None); return await event.respond("❌ عملیات لغو شد.",buttons=(await render())[1])
   try:
    if field=="force_join_channel_id":
     channel_id=int(value); perms=await event.client.get_permissions(channel_id,"me")
     if not getattr(perms,"is_admin",False): raise ValueError("ربات در این کانال ادمین نیست. ابتدا ربات را به کانال اضافه و ادمین کنید، سپس آیدی کانال را ارسال کنید.")
     await SERVICE.set(field,str(channel_id))
    else: await SERVICE.set(field,value)
   except ValueError as exc:return await event.respond(f"❌ {exc}\n\nمقدار را اصلاح کنید یا `/cancel` بزنید.")
   except Exception:return await event.respond("❌ کانال قابل بررسی نیست. مطمئن شوید ربات داخل کانال است و دسترسی ادمین دارد.")
   INPUTS.pop(key,None); text,buttons=await render(); await event.respond("✅ تنظیمات ذخیره شد.",buttons=buttons)
 client.add_event_handler(cb,events.CallbackQuery(func=lambda e:bool(e.data and e.data.startswith(PREFIX))))
 client.add_event_handler(msg,events.NewMessage(incoming=True))
async def _auth(event):return bool(event.is_private and get_tenant() and await RepresentativeDashboardService().is_owner(event.sender_id))
async def render():
 s=await SERVICE.snapshot(); brand=s["brand"] or "پیش‌فرض ثبت‌نام"; support=("@"+s["support_username"]) if s["support_username"] else "تنظیم نشده"; card=s["payment_card_number"] or "تنظیم نشده"; holder=s["payment_card_holder"] or "تنظیم نشده"; mode=s.get("referral_reward_mode","none"); rv=s.get("referral_reward_value","0"); reward="خاموش" if mode=="none" else (f"{rv} تومان برای ورود" if mode=="fixed" else f"{rv}% از خریدها"); channel=s.get("force_join_channel_id") or "تنظیم نشده"
 text=("⚙️ **تنظیمات نماینده**\n\n" f"🏷 برند: **{brand}**\n🆘 پشتیبانی: **{support}**\n🌍 منطقه زمانی: **{s['timezone']}**\n\n💳 **اطلاعات پرداخت فروشگاه**\n💳 شماره کارت: **{card}**\n👤 به نام: **{holder}**\n\n👥 **پاداش دعوت دوستان**\n🎁 وضعیت: **{reward}**\n\n📢 **جوین اجباری کانال**\n📌 کانال: **{channel}**")
 return text,[[Button.inline("🏷 ویرایش برند",PREFIX+b"edit:brand")],[Button.inline("🆘 پشتیبانی",PREFIX+b"edit:support_username")],[Button.inline("🌍 منطقه زمانی",PREFIX+b"edit:timezone")],[Button.inline("💳 شماره کارت",PREFIX+b"edit:payment_card_number")],[Button.inline("👤 نام صاحب کارت",PREFIX+b"edit:payment_card_holder")],[Button.inline("🎁 پاداش دعوت",PREFIX+b"referral")],[Button.inline("📢 جوین اجباری کانال",PREFIX+b"forcejoin")],[Button.inline("🔄 تازه‌سازی",PREFIX+b"list")],[Button.inline("📊 داشبورد",b"rep:"+REP_HOME.encode())]]
async def handle(event):
 action=(event.data[len(PREFIX):] if event.data.startswith(PREFIX) else b"").decode(errors="ignore"); key=(get_tenant(),event.sender_id)
 if action.startswith("edit:"):
  field=action[5:]; prompts={"brand":"🏷 نام برند جدید را ارسال کنید:","support_username":"🆘 یوزرنیم پشتیبانی را ارسال کنید (مثال: support):","timezone":"🌍 منطقه زمانی را ارسال کنید (مثال: Asia/Tehran):","payment_card_number":"💳 شماره کارت ۱۶ رقمی را ارسال کنید:","payment_card_holder":"👤 نام و نام خانوادگی صاحب کارت را ارسال کنید:"}
  if field not in prompts:return await event.answer("تنظیم نامعتبر است.",alert=True)
  INPUTS[key]=field; return await event.edit(prompts[field]+"\n\nبرای لغو `/cancel`",buttons=[[Button.inline("❌ لغو",PREFIX+b"list")]])
 if action=="referral":
  s=await SERVICE.snapshot(); mode=s.get("referral_reward_mode","none"); value=s.get("referral_reward_value","0"); label="خاموش" if mode=="none" else (f"ورود: {value} تومان" if mode=="fixed" else f"خرید: {value}%")
  return await event.edit("🎁 **تنظیم پاداش دعوت**\n\n" f"وضعیت فعلی: **{label}**\n\nنوع پاداش را انتخاب کنید:",buttons=[[Button.inline("💵 مبلغ ثابت هنگام ورود",PREFIX+b"refmode:fixed")],[Button.inline("📈 درصد از هر خرید",PREFIX+b"refmode:percent")],[Button.inline("⛔ خاموش",PREFIX+b"refmode:none")],[Button.inline("🔙 تنظیمات",PREFIX+b"list")]])
 if action.startswith("refmode:"):
  mode=action.split(":",1)[1]; await SERVICE.set("referral_reward_mode",mode)
  if mode=="none": await SERVICE.set("referral_reward_value","0"); text,buttons=await render(); return await event.edit(text,buttons=buttons)
  INPUTS[key]="referral_reward_value"; prompt="💵 مبلغ ثابت پاداش را به تومان ارسال کنید:" if mode=="fixed" else "📈 درصد پاداش از هر خرید را ارسال کنید (۰ تا ۱۰۰):"; return await event.edit(prompt+"\n\nبرای لغو `/cancel`",buttons=[[Button.inline("❌ لغو",PREFIX+b"list")]])
 if action=="forcejoin":
  return await event.edit("📢 **تنظیم جوین اجباری**\n\n۱) همین ربات را ابتدا داخل کانال اضافه و **ادمین** کنید.\n۲) سپس آیدی عددی کانال را ارسال کنید؛ مثال: `-1001234567890`\n۳) ربات بررسی می‌کند که خودش ادمین کانال باشد و فقط در صورت تأیید تنظیم ذخیره می‌شود.\n\nبرای لغو `/cancel`",buttons=[[Button.inline("🗑 حذف جوین اجباری",PREFIX+b"forcejoin:clear")],[Button.inline("🔙 تنظیمات",PREFIX+b"list")]])
 if action=="forcejoin:clear":
  await SERVICE.set("force_join_channel_id",""); text,buttons=await render(); return await event.edit(text,buttons=buttons)
 if action=="list": text,buttons=await render(); return await event.edit(text,buttons=buttons)
 return await event.answer("گزینه نامعتبر است.",alert=True)

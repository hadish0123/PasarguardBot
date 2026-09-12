from __future__ import annotations
from telethon import Button, events
from app.core.ids import REP_DISCOUNTS, REP_HOME, REP_LINKS, REP_LOGS, REP_ORDERS, REP_PANEL, REP_PLANS, REP_SALES, REP_SERVICES, REP_SETTINGS, REP_SUPPORT, REP_TEXTS, REP_USERS
from app.runtime.context import get_tenant
from app.runtime.dispatcher import tenant_dispatch
from app.services.representative_dashboard import RepresentativeDashboardService
SERVICE=RepresentativeDashboardService(); PREFIX=b"rep:"
ADMIN_MENU=[[Button.inline("📊 داشبورد",PREFIX+REP_HOME.encode())],[Button.inline("🗂 مدیریت پلن‌ها",PREFIX+REP_PLANS.encode()),Button.inline("👥 کاربران",PREFIX+REP_USERS.encode())],[Button.inline("🛒 فروش و سفارش‌ها",PREFIX+REP_ORDERS.encode())],[Button.inline("🔌 مدیریت سرویس‌ها",PREFIX+REP_SERVICES.encode())],[Button.inline("🎟 تخفیف‌ها",PREFIX+REP_DISCOUNTS.encode()),Button.inline("⚙️ تنظیمات فروش",PREFIX+REP_SALES.encode())],[Button.inline("🔌 اتصال پنل پاسارگارد",PREFIX+REP_PANEL.encode())],[Button.inline("🆘 تیکت‌های پشتیبانی",PREFIX+REP_SUPPORT.encode())],[Button.inline("📝 متن‌ها و دکمه‌ها",PREFIX+REP_TEXTS.encode())],[Button.inline("📋 لاگ‌ها",PREFIX+REP_LOGS.encode()),Button.inline("🔗 لینک‌ها",PREFIX+REP_LINKS.encode())],[Button.inline("⚙️ تنظیمات نماینده",PREFIX+REP_SETTINGS.encode())],[Button.inline("📘 راهنمای مدیریت ربات",PREFIX+b"guide")]]
def register(client,tenant_id=None):
 async def callback(event):
  async with tenant_dispatch(tenant_id): await admin_callback(event)
 client.add_event_handler(show_admin,events.NewMessage(pattern=r"^/admin$")); client.add_event_handler(callback,events.CallbackQuery())
async def _authorized(event): return bool(event.is_private and get_tenant() and await SERVICE.is_owner(event.sender_id))
async def dashboard_text():
 d=await SERVICE.snapshot(); bot=f"@{d['bot_username']}" if d['bot_username'] else "در حال شناسایی"; return f"📊 **داشبورد نماینده**\n\n🏷 برند: **{d['brand']}**\n🤖 ربات: **{bot}**\n🟢 وضعیت: **فعال**\n\nاز منوی زیر مدیریت فروشگاه و سرویس‌های نمایندگی را انجام دهید."
async def show_admin(event):
 if await _authorized(event): await event.respond(await dashboard_text(),buttons=ADMIN_MENU)
async def admin_callback(event):
 data=event.data
 if not data or not data.startswith(PREFIX): return
 if not await _authorized(event): return await event.answer("دسترسی مدیریت ندارید.",alert=True)
 if data.startswith(b"rep:orders:"):
  from app.telegram.representative.orders import callback_handler
  return await callback_handler(event)
 child=(b"rep:plans:",b"rep:users:",b"rep:services:",b"rep:discounts:",b"rep:sales:",b"rep:texts:",b"rep:logs:",b"rep:links:",b"rep:settings:",b"rep:panel:",b"rep:support:")
 if data.startswith(child): return
 action=data[len(PREFIX):].decode(errors="ignore")
 if action==REP_HOME: t,b=await _page("admin"); await event.edit(t,buttons=b); return await event.answer()
 if action=="guide":
  return await _show_guide(event,0)
 if action.startswith("guide:"):
  try: page=int(action.split(":",1)[1])
  except ValueError: page=0
  return await _show_guide(event,page)
 pages={REP_PLANS:"plans",REP_USERS:"users",REP_ORDERS:"orders",REP_SERVICES:"services",REP_DISCOUNTS:"discounts",REP_SALES:"sales",REP_TEXTS:"texts",REP_LOGS:"logs",REP_LINKS:"links",REP_SETTINGS:"settings",REP_PANEL:"panel"}
 if action in pages: t,b=await _page(pages[action]); await event.edit(t,buttons=b); return await event.answer()
 if action==REP_SUPPORT:
  from app.telegram.representative.support_admin import render
  await render(event); return await event.answer()
 await event.answer("گزینه نامعتبر است.",alert=True)
async def _page(name):
 if name=="admin": return await dashboard_text(),ADMIN_MENU
 mod=__import__(f"app.telegram.representative.{name}",fromlist=["render"]); return await mod.render()

_GUIDE_PAGES=[
("🏁 شروع کار", "به ربات نمایندگی خوش آمدید. این پنل برای مدیریت کامل فروشگاه، کاربران، سفارش‌ها و سرویس‌های شماست.\n\n📌 ابتدا از «🗂 مدیریت پلن‌ها» پلن‌های فروش را بسازید و برای هر پلن Template مناسب پاسارگارد را تنظیم کنید.\n\n📌 سپس «🔌 اتصال پنل پاسارگارد» را بررسی کنید تا اتصال سرویس‌دهنده آماده باشد.\n\n📌 از «⚙️ تنظیمات نماینده» برند، پشتیبانی، پرداخت، جوین اجباری، پاداش دعوت و سرویس تستی را تنظیم کنید."),
("📊 داشبورد", "داشبورد صفحه اصلی مدیریت است و اطلاعات کلی نمایندگی و وضعیت ربات را نشان می‌دهد.\n\n🔙 هر زمان از بخش‌های مختلف به داشبورد برگردید، منوی کامل مدیریت در دسترس است."),
("🗂 مدیریت پلن‌ها", "برای ساخت پلن جدید روی «➕ ساخت پلن» بزنید و نام، حجم، مدت، قیمت و Template پاسارگارد را وارد کنید.\n\n✏️ هر پلن را می‌توانید ویرایش کنید.\n🔄 با تغییر وضعیت، پلن فعال یا غیرفعال می‌شود.\n🗑 حذف پلنی که سابقه سفارش یا سرویس داشته باشد توسط سیستم جلوگیری می‌شود.\n\n💡 Template باید با پلنی که در پاسارگارد برای ساخت سرویس استفاده می‌شود هماهنگ باشد."),
("👥 کاربران", "در مدیریت کاربران می‌توانید کاربران فروشگاه خود را جستجو و مدیریت کنید.\n\n🔎 جستجو با Telegram ID، یوزرنیم یا نام\n👤 مشاهده جزئیات کاربر\n🚫 مسدود یا فعال کردن کاربر\n💰 افزایش موجودی\n💸 کاهش موجودی\n\n⚠️ تغییر موجودی مالی را فقط در صورت نیاز و با دقت انجام دهید."),
("🛒 فروش و سفارش‌ها", "این بخش برای پیگیری فروش‌هاست.\n\n📋 سفارش‌ها را بر اساس «همه»، «در انتظار»، «پرداخت‌شده»، «تکمیل‌شده» و «لغوشده» ببینید.\n\n💳 سفارش در انتظار را می‌توانید تأیید یا لغو کنید.\n🔌 سفارش پرداخت‌شده را برای تحویل سرویس پردازش کنید.\n📦 پس از تحویل، وضعیت سفارش را تکمیل کنید.\n\n🔔 هنگام تحویل موفق، اطلاعات سرویس برای کاربر ارسال می‌شود."),
("🔌 مدیریت سرویس‌ها", "در این بخش سرویس‌های ایجادشده را مدیریت می‌کنید.\n\n📋 فیلترهای فعال، در انتظار تحویل، در حال ساخت، منقضی و لغوشده در دسترس هستند.\n🔄 برای سرویس‌های در انتظار یا در حال ساخت می‌توانید تحویل را دوباره اجرا کنید.\n⚫ سرویس فعال را می‌توان منقضی ثبت کرد.\n🔴 لغو دسترسی، وضعیت سرویس را در سیستم فروش لغوشده می‌کند."),
("🎟 تخفیف‌ها", "برای ایجاد و مدیریت تخفیف‌های فروشگاه استفاده می‌شود.\n\n💡 قبل از تبلیغ یک کد تخفیف، تاریخ اعتبار، محدودیت استفاده و پلن‌های مشمول را بررسی کنید.\n\nهدف این بخش کنترل تخفیف‌ها بدون نیاز به تغییر دستی سفارش‌هاست."),
("⚙️ تنظیمات فروش", "تنظیمات مرتبط با فرآیند فروش و پرداخت فروشگاه در این بخش قرار دارد.\n\n📌 قبل از شروع فروش واقعی، مقادیر این بخش را بررسی کنید تا قیمت‌گذاری و فرآیند پرداخت مطابق سیاست فروش شما باشد."),
("🔌 اتصال پنل پاسارگارد", "این بخش وضعیت اتصال نمایندگی به پنل پاسارگارد را مدیریت می‌کند.\n\n📌 آدرس پنل و اطلاعات اتصال را صحیح وارد کنید.\n🔄 در صورت خطای اتصال، ابتدا آدرس، دسترسی API و اطلاعات احراز هویت را بررسی کنید.\n\n🔐 اطلاعات حساس را برای افراد دیگر ارسال نکنید."),
("🆘 تیکت‌های پشتیبانی", "تیکت‌ها برای پیگیری درخواست‌های پشتیبانی کاربران استفاده می‌شوند.\n\n📨 تیکت جدید را باز کنید، پاسخ دهید و پس از حل مشکل آن را ببندید.\n📌 بهتر است پاسخ‌ها شامل توضیح کوتاه، دقیق و مرحله بعدی کاربر باشند."),
("📝 متن‌ها و دکمه‌ها", "برای شخصی‌سازی متن‌ها و دکمه‌های ربات استفاده می‌شود.\n\n💡 متن‌ها را کوتاه، واضح و متناسب با برند خود نگه دارید.\n⚠️ در صورت وجود متغیر یا قالب خاص در متن، ساختار آن را تغییر ندهید مگر اینکه مطمئن باشید."),
("📋 لاگ‌ها", "لاگ‌ها برای بررسی فعالیت‌ها و خطاهای مدیریتی هستند.\n\n🔎 هنگام بروز مشکل ابتدا زمان تقریبی و عملیات انجام‌شده را مشخص کنید، سپس لاگ مربوط را بررسی کنید.\n\n⚠️ اطلاعات حساس مانند Token را در اختیار دیگران قرار ندهید."),
("🔗 لینک‌ها", "این بخش برای مدیریت لینک‌های مرتبط با فروشگاه و نمایندگی است.\n\n📌 لینک‌های فروش، پشتیبانی یا معرفی را بررسی کنید و از قرار دادن لینک اشتباه در پیام‌های عمومی خودداری کنید."),
("⚙️ تنظیمات نماینده", "مهم‌ترین تنظیمات اختصاصی نماینده اینجا قرار دارد:\n\n🏷 برند و نام فروشگاه\n🆘 یوزرنیم پشتیبانی\n🌍 منطقه زمانی\n💳 شماره کارت و نام صاحب کارت\n🎁 پاداش دعوت دوستان (مبلغ ثابت یا درصد خرید)\n📢 جوین اجباری کانال\n🎁 سرویس تستی\n\n🎁 سرویس تستی شامل فعال/غیرفعال کردن، حجم MB/GB، مدت و ریست کاربران استفاده‌کننده است."),
("🔐 نکات مهم مدیریت", "🔒 اطلاعات ورود و Token پاسارگارد را محرمانه نگه دارید.\n\n💳 قبل از تأیید دستی پرداخت، مبلغ و اطلاعات سفارش را بررسی کنید.\n\n🗂 قبل از حذف یا تغییر پلن، اثر آن روی فروش و سرویس‌های قبلی را بررسی کنید.\n\n📢 اگر جوین اجباری فعال است، ربات باید در کانال ادمین باشد.\n\n🆘 اگر سرویس ساخته نشد، ابتدا اتصال پاسارگارد و Template پلن را بررسی و سپس از گزینه «تحویل / تلاش مجدد» استفاده کنید."),
]

async def _show_guide(event,page:int=0):
 page=max(0,min(page,len(_GUIDE_PAGES)-1))
 title,body=_GUIDE_PAGES[page]
 text=f"📘 **راهنمای کامل مدیریت ربات نمایندگی**\n\n{title}\n\n{body}\n\n📖 بخش **{page+1} از {len(_GUIDE_PAGES)}**"
 rows=[]
 nav=[]
 if page>0: nav.append(Button.inline("⬅️ قبلی",PREFIX+f"guide:{page-1}".encode()))
 if page+1<len(_GUIDE_PAGES): nav.append(Button.inline("بعدی ➡️",PREFIX+f"guide:{page+1}".encode()))
 if nav: rows.append(nav)
 rows.append([Button.inline("🏠 منوی مدیریت",PREFIX+REP_HOME.encode())])
 await event.edit(text,buttons=rows)
 return await event.answer()

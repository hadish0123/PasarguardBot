# A-01 — Representative Dashboard

## هدف

داشبورد اولین صفحه واقعی ربات نمایندگی است و فقط مالک Tenant را به بخش مدیریت وارد می‌کند.

## ورود

- `/start` در Bot نمایندگی
- `/admin` در Bot نمایندگی
- دکمه `📊 داشبورد`

## کنترل دسترسی

- پیام باید private باشد.
- Tenant از `ContextVar` خوانده می‌شود.
- `sender_id` باید برابر `TenantRecord.owner_id` باشد.
- Tenant باید `active` باشد.
- کاربر عادی هرگز داشبورد نماینده را دریافت نمی‌کند و به User Home می‌رود.

## محتوای صفحه

- نام برند
- username ربات
- وضعیت فعال
- منوی کامل مدیریت نماینده

## دکمه‌ها

- `📊 داشبورد` → بازخوانی همین صفحه
- `🗂 مدیریت پلن‌ها` → A-02
- `👥 کاربران` → A-03
- `🛒 فروش و سفارش‌ها` → A-04
- `🎟 تخفیف‌ها` → A-05
- `⚙️ تنظیمات فروش` → A-06
- `📝 متن‌ها و دکمه‌ها` → A-07
- `📋 لاگ‌ها` → A-08
- `🔗 لینک‌ها` → A-09
- `⚙️ تنظیمات نماینده` → A-10

در نسخه فعلی مقصدهای A-02 تا A-10 عمداً به‌عنوان صفحات بعدی باقی مانده‌اند؛ هیچ داده یا credential ساختگی نمایش داده نمی‌شود.

## Scope

تمام خواندن‌ها tenant-scoped هستند و Dashboard Service مستقیماً Tenant ID فعلی را از runtime context می‌گیرد.

## فایل‌ها

- `app/services/representative_dashboard.py`
- `app/telegram/representative/runtime.py`
- `app/telegram/representative/admin.py`
- `app/telegram/representative/user.py`
- `app/runtime/context.py`
- `app/runtime/dispatcher.py`

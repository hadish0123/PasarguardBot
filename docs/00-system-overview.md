# PasarguardBot — System Overview

## هدف
این مستندات نقشه مرجع پروژه را قبل از بازطراحی Runtime نمایندگان ثبت می‌کند. هدف این است که طراحی جدید بر پایه قابلیت‌های موجود انجام شود، نه با ساخت یک سیستم بی‌ارتباط با سورس فعلی.

## مرز سیستم

```text
Central Bot
  └─ ثبت و مدیریت ربات‌های نماینده

Representative Bot #N
  ├─ پنل مدیریت نماینده
  ├─ پنل کاربر
  ├─ فروش و خرید سرویس
  ├─ مدیریت پلن‌ها
  ├─ مدیریت کاربران
  ├─ تخفیف‌ها
  ├─ تنظیمات فروش
  ├─ متن‌ها و دکمه‌ها
  ├─ لاگ‌ها
  └─ اتصال به Panel/Pasarguard نماینده
```

## اصل معماری هدف
- Central Bot نباید پنل فروش نماینده باشد.
- هر Representative Bot یک Runtime کامل و مستقل است.
- داده‌های هر نماینده در Tenant Database خودش قرار می‌گیرد.
- کاربر فقط با Representative Bot مربوط به خودش کار می‌کند.
- Admin نماینده فقط داده‌های Tenant خودش را می‌بیند.
- منطق مشترک باید reusable باشد، اما registration و routing نباید باعث تداخل Central و Representative شوند.

## منابع فعلی که مبنای طراحی هستند
- `app/custom_telethon/`
- `app/runtime/`
- `app/multibot/`
- `app/telegram/admin/representative_panel/`
- `app/telegram/user/`
- `app/telegram/admin/`
- `app/db/`
- `app/services/`
- `app/config.py`

## فازهای کار
1. تثبیت معماری و قراردادها.
2. طراحی صفحه‌به‌صفحه پنل مدیریت نماینده.
3. طراحی صفحه‌به‌صفحه پنل کاربر.
4. طراحی جریان ثبت ربات نماینده در Central.
5. پیاده‌سازی Runtime نماینده.
6. اتصال هر صفحه به handler/service/database واقعی.
7. تست مسیرهای کامل و regression.

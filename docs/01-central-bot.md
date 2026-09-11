# Central Bot

## مسئولیت
Central Bot فقط لایه ثبت، احراز و مدیریت چرخه عمر Representative Botهاست.

## صفحه‌ها

### C-01 — صفحه شروع
- معرفی سرویس
- ثبت ربات نماینده
- وضعیت ثبت فعلی

### C-02 — ثبت ربات نماینده
ورودی‌ها:
- Telegram Bot Token
- اطلاعات مالک
- مشخصات اولیه نماینده

خروجی:
- ساخت registration
- رمزنگاری Token/API credentials
- ایجاد Tenant در مرحله provisioning

### C-03 — وضعیت درخواست
وضعیت‌ها:
- pending
- approved
- rejected
- provisioning
- active
- failed
- disabled

### C-04 — مدیریت نمایندگان برای Super Admin
- لیست نمایندگان
- فعال/غیرفعال کردن
- مشاهده وضعیت Runtime
- مشاهده خطاهای provisioning
- بازنشانی/راه‌اندازی مجدد Runtime

## Central نباید انجام دهد
- ساخت پلن فروش نماینده
- فروش سرویس نماینده
- مدیریت کاربران نماینده
- مدیریت موجودی کاربران نماینده
- نمایش پنل مدیریت فروش نماینده

## داده‌های مرکزی
اطلاعاتی مثل registration، tenant identity، bot identity، encrypted credentials و lifecycle state در Central DB باقی می‌مانند.

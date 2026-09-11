# C-04 — Representative Tenant Provisioning

## هدف

پس از تأیید درخواست در C-03، نماینده باید بدون دخالت دستی به یک Tenant مستقل منطقی، credentialهای رمزنگاری‌شده و یک Telegram runtime اختصاصی دسترسی پیدا کند.

## جریان کامل

1. C-03 وضعیت درخواست را از `pending` به `provisioning` تغییر می‌دهد.
2. `ProvisioningService` رکورد ثبت را دوباره می‌خواند تا اجرای تکراری امن باشد.
3. وجود تمام داده‌های لازم بررسی می‌شود.
4. Token ربات و API Key پنل فقط از SecretBox رمزگشایی می‌شوند.
5. `TenantService.provision()` رکورد Tenant را ایجاد یا به‌روزرسانی می‌کند.
6. `RepresentativeRuntimeRegistry` دقیقاً یک runtime برای Tenant اجرا می‌کند.
7. Telethon با Bot Token اتصال واقعی را برقرار می‌کند.
8. `get_me()` هویت واقعی Bot را بررسی می‌کند.
9. username واقعی در Tenant ذخیره می‌شود.
10. Tenant به `active` و Registration به `active` می‌روند.
11. مالک پیام فعال‌شدن و username ربات را دریافت می‌کند.

## خطا و Retry

اگر هر مرحله بعد از ایجاد Tenant شکست بخورد:

- runtime متوقف می‌شود؛
- Tenant به `failed` می‌رود؛
- Registration به `failed` می‌رود؛
- credentialهای رمزنگاری‌شده حذف نمی‌شوند؛
- Admin می‌تواند عملیات را Retry کند.

## Idempotency

`registration_id` در `representative_tenants` unique است. اجرای دوباره provisioning برای همان درخواست Tenant دوم ایجاد نمی‌کند و رکورد موجود را به‌روزرسانی می‌کند.

## امنیت

Token و Panel API Key در DB به‌صورت plaintext ذخیره نمی‌شوند و در UI مرکزی نیز نمایش داده نمی‌شوند.

## Scope داده

Tenant registry در DB مرکزی نگهداری می‌شود و تمام runtimeهای نمایندگی با `tenant_id` وارد context می‌شوند. این لایه مرجع lifecycle است؛ جداول دامنه فروش و کاربران باید در مراحل بعدی با همین tenant scope ساخته شوند.

## دکمه‌ها و وضعیت‌ها

- `تأیید و شروع راه‌اندازی` → provisioning
- `تلاش مجدد راه‌اندازی` → retrying → provisioning
- `بازگشت` → C-03
- success → active
- failure → failed

## فایل‌های اصلی

- `app/services/provisioning.py`
- `app/services/tenant.py`
- `app/services/registration_store.py`
- `app/telegram/representative/registry.py`
- `app/telegram/representative/runtime.py`
- `app/telegram/central/admin.py`
- `app/db/models.py`

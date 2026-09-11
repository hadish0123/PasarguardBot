# A-11 — وضعیت اتصال پنل پاسارگارد

## PAGE ID
`A-11`

## Purpose
نمایش وضعیت اتصال نماینده به پنل پاسارگارد و اجرای تست واقعی اتصال، بدون نمایش کلید API.

## Entry Points
- داشبورد نماینده → `🔌 اتصال پنل پاسارگارد`
- callback: `rep:rep.panel`

## Required Permission
- چت خصوصی Telegram
- نماینده فعال
- مالک همان tenant

## UI Structure
### Header
`🔌 وضعیت اتصال پنل پاسارگارد`

### Body
- وضعیت اتصال
- آدرس پنل
- نام کاربری پنل
- وضعیت tenant
- پیام نتیجه تست
- یادآوری اینکه API key نمایش داده نمی‌شود

### Footer
- `🔄 تست اتصال`
- `📋 نمایش دوباره`
- `📊 داشبورد`

## Buttons
| Button | Callback | Action | Result |
|---|---|---|---|
| تست اتصال | `rep:panel:check` | اجرای health check | نمایش connected/unreachable/unauthorized/missing |
| نمایش دوباره | `rep:panel:list` | بارگذاری snapshot | نمایش صفحه |
| داشبورد | `rep:rep.home` | برگشت | داشبورد نماینده |

## States
- `checking`: در حال اجرای درخواست HTTP
- `connected`: پاسخ موفق
- `unreachable`: خطای شبکه/HTTP غیرموفق
- `unauthorized`: HTTP 401/403
- `missing`: تنظیمات اتصال ناقص
- `unknown`: هنوز تست نشده
- `error`: خطای داخلی

## Security
- API key فقط از storage رمزنگاری‌شده decrypt می‌شود.
- API key هرگز در Telegram render یا log نمی‌شود.
- تمام خواندن‌ها tenant-scoped هستند.

## Data
`TenantRecord.panel_url`, `panel_username`, `panel_api_key_encrypted`, `status`.

## Services
- `PanelStatusService`
- `PasarguardClient`
- `SecretBox/Fernet`
- SQLAlchemy

## Source Mapping
- Service: `app/services/panel_status.py`
- HTTP client: `app/services/pasarguard.py`
- Telegram page: `app/telegram/representative/panel.py`
- Runtime registration: `app/telegram/representative/runtime.py`
- Admin routing: `app/telegram/representative/admin.py`
- Page registry: `app/rebuild/page_registry.py`

# Runtime و Routing

## هدف
جلوگیری از تداخل handlerهای Central و Representative.

## Runtime lifecycle
```text
Registration
  ↓
Provision Tenant
  ↓
Load credentials
  ↓
Create bot client
  ↓
Set tenant context
  ↓
Register representative modules
  ↓
Start polling/event loop
  ↓
Health monitoring
```

## Routing layers
1. Telegram event
2. Runtime identity
3. Tenant context
4. Authentication/authorization
5. Feature handler
6. Service layer
7. Tenant DB / Pasarguard API

## Handler ownership
### Central
فقط registration/lifecycle/admin-supervisor.

### Representative
تمام user/admin business flows.

## State machine
Stateهای conversation باید tenant-aware باشند و key آن‌ها نباید باعث اشتراک ناخواسته بین نمایندگان شود.

## StopPropagation
Dispatcher باید stop شدن event را به‌عنوان کنترل جریان داخلی مدیریت کند و آن را به exception حل‌نشده در log تبدیل نکند.

## Input normalization
دکمه‌های فارسی باید قبل از routing normalize شوند؛ از جمله:
- فاصله
- نیم‌فاصله
- حروف عربی/فارسی
- variationهای emoji در صورت نیاز

## Rule
یک action نباید هم‌زمان توسط Central handler و Representative handler پردازش شود.

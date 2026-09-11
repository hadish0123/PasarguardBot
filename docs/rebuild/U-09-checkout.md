# U-09 — Checkout و پرداخت

## Purpose
جریان کامل خرید مشتری نماینده: انتخاب پلن، بازبینی مبلغ، اعمال/حذف کد تخفیف، ثبت سفارش و ثبت شناسه پرداخت.

## Entry Points
- U-01 → خرید
- U-05 → اعمال تخفیف در Checkout
- callbackهای `user:order:<plan_id>`

## Permission
- چت خصوصی Telegram
- مشتری متعلق به tenant جاری
- کاربر blocked اجازه ورود ندارد.

## UI Contract
### Review
- پلن، حجم، مدت، مبلغ پایه
- کد تخفیف در صورت وجود
- مقدار تخفیف
- مبلغ نهایی
- پرداخت و ثبت سفارش
- اعمال کد تخفیف
- حذف تخفیف
- بازگشت به پلن‌ها
- لغو

### Discount Input
- ورودی متن کد تخفیف
- نرمال‌سازی به uppercase
- خطای کد ناموجود/غیرفعال/منقضی/تمام‌شده
- `/cancel` برای خروج

### Payment
پس از ایجاد سفارش، مشتری شناسه پرداخت یا کد پیگیری را ارسال می‌کند. این شناسه در CheckoutRecord ذخیره می‌شود.

اگر `require_payment_confirmation` فعال باشد، سفارش در وضعیت انتظار تأیید مدیریت باقی می‌ماند. در غیر این صورت پس از ثبت شناسه پرداخت به `paid` می‌رود.

## Data Contract
### Order
- tenant_id
- telegram_user_id
- plan snapshot
- amount = مبلغ نهایی
- status = pending / paid / fulfilled / cancelled

### CheckoutRecord
- tenant_id
- order_id
- telegram_user_id
- subtotal
- discount_amount
- total
- discount_code
- payment_reference
- payment_submitted_at

### DiscountRedemption
- tenant_id
- discount_id
- order_id
- telegram_user_id
- amount

تمام داده‌ها tenant-scoped هستند.

## Settings
- `sales_enabled`: جلوگیری از ثبت خرید جدید
- `require_payment_confirmation`: نیاز به تأیید مدیریت
- `allow_pending_orders`: تنظیم فروش؛ اتصال کامل آن به سیاست سفارش در مرحله بعدی payment/fulfillment تکمیل می‌شود.
- `currency`: واحد نمایش مبلغ

## Error States
- پلن غیرفعال یا حذف‌شده
- فروش غیرفعال
- کد تخفیف نامعتبر
- سقف مصرف تخفیف تکمیل‌شده
- سفارش ناموجود
- شناسه پرداخت نامعتبر
- وضعیت سفارش غیرقابل پرداخت
- خطای دیتابیس

## Source Mapping
- `app/telegram/representative/navigation.py` — customer navigation
- `app/telegram/representative/checkout.py` — checkout UI and input handling
- `app/services/orders.py` — transactional checkout and payment submission
- `app/services/discounts.py` — discount validation/calculation
- `app/services/sales_settings.py` — tenant sales policy
- `app/db/models.py` — Order / CheckoutRecord / DiscountRedemption

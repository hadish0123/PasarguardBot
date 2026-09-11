# A-02 — Plan Management

## دسترسی

فقط مالک Tenant فعال در private chat.

## عملیات

- نمایش لیست پلن‌ها
- ساخت پلن با wizard چهارمرحله‌ای
- مشاهده جزئیات
- فعال/غیرفعال کردن
- حذف با تأیید دو مرحله‌ای
- بازگشت به داشبورد
- لغو wizard

## Wizard ساخت

1. نام — 2 تا 120 کاراکتر
2. حجم — عدد اعشاری مثبت، مثل `0.5`
3. مدت — عدد صحیح مثبت روز
4. قیمت — عدد صفر یا مثبت

هر ورودی نامعتبر همان مرحله را حفظ می‌کند و پیام خطا می‌دهد. `لغو` و `/cancel` wizard را می‌بندند.

## Scope

هر Plan دارای `tenant_id` است و تمام queryها علاوه بر `plan_id`، Tenant فعلی را الزام می‌کنند. بنابراین نماینده‌ای نمی‌تواند پلن Tenant دیگر را مشاهده، تغییر یا حذف کند.

## وضعیت‌ها

- empty
- listing
- creating_name
- creating_volume
- creating_days
- creating_price
- created
- confirm_delete
- error

## فایل‌ها

- `app/db/models.py` → `Plan`
- `app/services/plans.py`
- `app/telegram/representative/plans.py`
- `app/runtime/dispatcher.py`

# Page-by-Page Design Plan

این فایل قرارداد طراحی UI/UX مرحله بعد است.

## مرحله 1 — Central
- C-01 Home
- C-02 Register Representative
- C-03 Registration Status
- C-04 Representative Management

## مرحله 2 — Representative Admin
- A-01 Dashboard
- A-02 Plans List
- A-03 Create Plan Wizard
- A-04 Edit Plan
- A-05 Users
- A-06 User Details
- A-07 Orders
- A-08 Sales Settings
- A-09 Discounts
- A-10 Texts & Buttons
- A-11 Logs
- A-12 Ready Links
- A-13 Representative Settings

## مرحله 3 — Representative User
- U-01 Home
- U-02 Service Selection
- U-03 Plan Selection
- U-04 Custom Purchase
- U-05 Purchase Confirmation
- U-06 Payment Result
- U-07 My Services
- U-08 Service Details
- U-09 Wallet
- U-10 Transactions
- U-11 Profile
- U-12 Support
- U-13 Referral
- U-14 Trial

## قالب طراحی هر صفحه
برای هر صفحه در مرحله طراحی ثبت می‌شود:
1. هدف صفحه
2. Entry points
3. Header
4. متن‌ها
5. Buttons
6. Button states
7. Empty state
8. Loading state
9. Error state
10. Confirmation state
11. Back navigation
12. Permission rules
13. DB data
14. Service/API calls
15. Success/failure transitions

## قانون
اول صفحه طراحی می‌شود، بعد mapping به فایل/handler فعلی مشخص می‌شود، سپس implementation انجام می‌شود. این کار اجازه می‌دهد UI بدون شکستن business logic بازطراحی شود.

# Tenant و Database

## اصل
هر Representative Runtime باید context مشخص داشته باشد و عملیات business با Tenant DB همان نماینده انجام شود.

```text
Central DB
   ├── Representative A → Tenant DB A
   ├── Representative B → Tenant DB B
   └── Representative C → Tenant DB C
```

## Central DB
برای lifecycle و identity نماینده:
- registration
- bot identity
- owner identity
- encrypted credentials
- tenant identity
- runtime status

## Tenant DB
برای business data:
- users
- panels
- plans
- purchases/orders
- balances
- discount codes
- settings
- keyboards/texts
- logs
- referral data
- service metadata

## Context contract
هر handler باید بتواند مشخص کند:
- آیا در Representative Runtime است؟
- Tenant فعلی چیست؟
- کاربر admin نماینده است یا user عادی؟

## Rule
هیچ query مربوط به business نماینده نباید ناخواسته به Central DB route شود.

# A-07 — Texts and Buttons

## Contract

The representative owner can inspect, edit, and reset tenant-scoped customer-facing texts and menu button labels.

### Permission
- Private chat only.
- Active representative owner only.
- Every read/write is scoped by the current tenant ID.

### UI states
1. **Listing:** all supported text/button keys are shown.
2. **Detail:** current effective value is shown (tenant override or default).
3. **Editing:** owner sends a replacement text; `/cancel` aborts.
4. **Saved:** override is persisted and immediately used by the customer menu/runtime.
5. **Reset:** the key is restored to its catalog default.
6. **Error:** invalid/empty/oversized input is rejected without changing the previous value.

## Supported catalog
- Welcome message
- Shop title and hint
- Blocked-user message
- Empty-plan message
- Buy title and hint
- Buy / My Services / Wallet / Profile / Referral / Discount / Trial / Support button labels

## Persistence
`representative_texts` uses `(tenant_id, key)` as a unique key. No tenant can read or modify another tenant's override through the service API.

## Runtime integration
The representative runtime loads the effective welcome text and customer button labels dynamically. This means an owner does not need a bot restart after saving a text.

## Validation
- Key must belong to the supported catalog.
- Value must be non-empty.
- Maximum length: 4000 characters.
- `/cancel` leaves the previous value unchanged.

## Files
- `app/db/models.py` — `RepresentativeText`
- `app/services/texts.py` — defaults, tenant persistence, reset
- `app/telegram/representative/texts.py` — owner UI and wizard
- `app/telegram/representative/user.py` — dynamic customer menu
- `app/telegram/representative/runtime.py` — dynamic welcome/blocked messages

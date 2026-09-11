# A-09 — Ready Links

Representative owners can maintain tenant-scoped quick links for support, panels, documentation, or other operational destinations.

## Flow
`🔗 لینک‌ها` → list → `➕ افزودن لینک` → title → URL → saved. Existing links can be deleted.

## Validation
- Title required, max 120 characters.
- URL must use HTTP or HTTPS.
- URL max 1000 characters.
- `/cancel` aborts the input wizard.

## Isolation
Every list/create/delete query includes the current tenant ID.

## Files
- `app/db/models.py` — `RepresentativeLink`
- `app/services/links.py` — CRUD and validation
- `app/telegram/representative/links.py` — Telegram UI

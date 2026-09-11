# A-08 — Audit Logs

The representative owner can inspect recent tenant-scoped audit events from the admin panel.

## States
- Loading
- Empty: no events yet
- Listing: newest events first
- Error: database failure without exposing secrets

## Events currently recorded
- `order.created`
- `order.status_changed`

The log record contains tenant ID, optional actor ID, action, bounded details, and timestamp. Bot tokens, API keys and other secrets are never written to the log.

## Navigation
`📋 لاگ‌ها` → list → refresh → dashboard.

## Permission
Private chat and active representative owner only.

## Files
- `app/db/models.py` — `RepresentativeLog`
- `app/services/logs.py` — tenant-scoped writer/reader
- `app/telegram/representative/logs.py` — Telegram UI
- `app/services/orders.py` — order audit events

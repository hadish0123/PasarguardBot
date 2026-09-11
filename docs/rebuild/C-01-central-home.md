# C-01 — Central Home

## Purpose
Private entry point of the central bot. It exposes only representative registration and owner-scoped registration tracking.

## Permission
- Telegram private chat only.
- A user can only read registration records where `owner_id == event.sender_id`.
- No central database record is exposed by tracking-code lookup across owners.

## UI
### Idle
- `🤖 ثبت ربات نمایندگی` → `central:register`
- `🔎 پیگیری درخواست` → `central:track:input`

### Request created / resumed
- Shows tracking code.
- `🔎 مشاهده وضعیت` → `central:track:latest`
- `🔙 بازگشت` → `central:home`

### Tracking input
- Accepts a tracking code such as `PG-A1B2C3D4`.
- `❌ لغو` → `central:cancel`.

### Status
Supports draft, pending, provisioning, active and rejected states. Rejection reason is shown when present.

### Empty
If the owner has no registration, the page reports that no request exists and returns to the main menu.

### Error
Database failures are converted to user-safe messages; implementation details are not exposed.

## Persistence
Table: `representative_registrations`.

C-01 reads/writes only the central database. Registration lookup is owner-scoped.

## Navigation contract
- `/start` → C-01
- `central:home` → C-01
- `central:register` → creates/resumes the owner draft and exposes its tracking code
- `central:track:input` → tracking input state
- `central:track:latest` → latest owner request status
- `central:cancel` → C-01

## Verification
Unit coverage exists for the home copy and active/rejected status rendering in `tests/test_central_home.py`.

The rebuild branch must still be executed through the project CI/runtime environment before production promotion; local network execution is not available in the assistant environment.

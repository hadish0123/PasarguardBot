# C-03 — Central Admin Representative Review

## Purpose
Central administrators review only `pending` representative registrations and transition them to `provisioning` or `rejected`.

## Entry
- `/admin` from the central bot.
- `⏳ درخواست‌های در انتظار` from the central dashboard.

## Permission
The Telegram sender must be present in `ADMIN_ID`. Every callback repeats the same authorization check.

## List state
- Loading: internal service call; failures return a safe error.
- Empty: `📭` no pending requests.
- Ready: one button per pending registration.

## Detail
Shows tracking code, owner, brand, Bot ID, panel URL, panel username and status. Secrets are never shown.

## Actions
### Approve
`approve:<registration_id>`
- Requires current status `pending`.
- Changes status to `provisioning`.
- Notifies the representative that provisioning has started.
- Actual tenant provisioning is deliberately the next lifecycle service, not hidden inside the UI handler.

### Reject
`reject_prompt:<registration_id>` asks the admin for a reason.
The admin submits `reject:<registration_id>:<reason>`.
- Reason must be at least 3 characters.
- Requires current status `pending`.
- Changes status to `rejected` and stores the reason.

## Security
- No bot token or API key is rendered.
- Non-admins receive no data from admin callbacks.
- The database transition checks the expected current status to prevent approving an already processed request.

## Navigation
Dashboard → Pending → Detail → Approve/Reject → Pending.

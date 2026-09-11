# C-02 — Representative Registration Wizard

## Flow
1. Brand
2. Bot Token
3. Bot ID confirmation
4. Pasarguard panel URL
5. Panel username
6. Panel API key
7. Review
8. Submit → pending admin review

## Security
- Bot Token and panel API key are encrypted with the Fernet key from `SECRET_KEY` before persistence.
- Secrets are never rendered back to the user.
- Tracking lookup is owner-scoped.
- Bot Token is verified with Telegram `getMe` before it is accepted.
- Panel URL + API key are checked against the Pasarguard system-info endpoint before submission.

## Navigation
- Continue → current persisted step.
- Previous → previous step without deleting already collected data.
- Cancel → exits the wizard without marking the request pending.
- Confirm → validates all required fields, marks the request `pending`, and notifies configured central admins.

## Validation
- Brand: 2–120 characters.
- Bot Token: Telegram Bot API validation.
- Bot ID: numeric and must equal the ID returned by Bot API.
- Panel URL: normalized HTTP(S) URL.
- Panel username: 2–190 characters, no spaces.
- API key: minimum length and live Pasarguard authentication check.

## Failure states
Every step returns a safe user-facing validation error and leaves the persisted step unchanged. External-service failures do not expose exception details.

## Persistence
`representative_registrations` stores the wizard step, non-secret metadata, encrypted Bot Token, encrypted panel API key, status, owner ID and tracking code.

## Operational requirement
The Railway environment must define `SECRET_KEY` as a valid Fernet key before this wizard is enabled in production.

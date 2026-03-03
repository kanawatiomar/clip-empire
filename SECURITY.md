# Security / Secrets Policy

## Never commit these
- `accounts/.master_key` (encryption key)
- `accounts/accounts.db` (encrypted credentials DB)
- `profiles/` (Chrome user-data dirs, cookies, sessions)
- `logs/` (may contain tokens/URLs)
- `renders/` and `data/` if they contain metadata tied to accounts

These are already included in `.gitignore`.

## Key management
- Back up `accounts/.master_key` offline (encrypted USB / password manager attachment).
- Losing the master key = losing access to all stored credentials.

## Operational safety
- Automate **post-login** tasks only. Avoid automating Google signup itself.
- Use per-channel Chrome profiles to avoid cross-account contamination.
- Keep concurrency low to reduce captchas/verification.

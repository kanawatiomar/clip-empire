# Clip Empire — Ops Runbook

## Daily workflow (target state)
1. Ingest sources
2. Generate candidates + score
3. Render final shorts (platform variants)
4. Publish (YouTube first, then TikTok/IG stagger)
5. QA sample + alert on failures
6. Bot Manager runs nightly optimization pass

---

## Account creation & verification (current reality)
Google aggressively rate-limits account creation:
- device/IP QR checks
- phone number reuse limits

Practical solutions:
- use a **fresh real carrier number** (prepaid SIM or carrier eSIM) for verification when needed
- avoid automation during signup; automate post-login tasks only

---

## Key commands (local)
```powershell
cd C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire\accounts
python manager.py list
python setup_wizard.py <channel>
python lockdown.py <channel>
```

---

## Failure classes (what to do)
### Captcha / verification
- pause that channel
- retry later with human-in-the-loop

### UI changes (selectors broke)
- patch platform-specific worker module
- add regression snapshots

### Upload failures
- backoff + retry
- after N failures → alert + pause

---

## What not to commit
- `profiles/`
- `accounts/.master_key`
- `accounts/accounts.db`

Add them to `.gitignore`.

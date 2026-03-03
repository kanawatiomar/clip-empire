# Clip Empire

Automated multi-channel short-form content pipeline (YouTube Shorts first, with TikTok + Instagram Reels cross-posting).

> Goal: scale to **50+ channels** and **500 uploads/day** (50×10/day) while continuously improving quality via analytics feedback loops.

## What’s in this repo

- `accounts/` — account database + encryption + setup/lockdown helpers
- `profiles/` — per-channel Chrome profiles (persistent login). **Do not commit.**
- `docs/` — master plan, architecture, operations, and runbooks

## Quick start (dev)

```powershell
cd C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Account ops

- Add an account after manual Google signup:
  ```powershell
  python accounts\setup_wizard.py <channel_name>
  ```

- Lock down (2FA + backup codes):
  ```powershell
  python accounts\lockdown.py <channel_name>
  ```

## Docs

Start here:
- `docs/MASTER_PLAN.md`
- `docs/ARCHITECTURE.md`
- `docs/OPS_RUNBOOK.md`
- `docs/CREATIVE_SYSTEM.md`
- `docs/OPENCLAW_AGENT_SETUP.md` (new dedicated OpenClaw operator setup)
- `docs/DISCORD_SERVER_BLUEPRINT.md` (new Discord server/channel structure + posting rules)
- `docs/DISCORD_BOOTSTRAP_CHECKLIST.md` (step-by-step server creation checklist)

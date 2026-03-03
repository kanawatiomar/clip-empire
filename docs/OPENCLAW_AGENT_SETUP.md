# OpenClaw Agent Setup (Dedicated Clip Empire Operator)

This guide is for spinning up a **new OpenClaw agent** dedicated to Clip Empire operations.

---

## 1) Purpose of this agent

The dedicated agent should do 4 things only:

1. Run the engine (`engine/`) and queue jobs
2. Run publisher worker (`publisher/`) and monitor outcomes
3. Post ops updates/alerts to Discord
4. Keep daily status logs clean and actionable

Avoid scope creep (random side tasks) in this session.

---

## 2) Machine setup checklist

On the deployment machine:

```powershell
cd C:\Users\kanaw\clip-empire
git pull
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install
python data\schema.py
python data\migrate.py
```

Optional sanity checks:

```powershell
python -m unittest engine.tests.test_new_features
python -m engine.cli --status
```

---

## 3) Required environment + local files

- `.env` (tokens/secrets)
- `accounts/.master_key` (critical encryption key)
- `profiles/<channel_name>/` persistent Chrome profiles
- Optional cookies for ingest:
  - `cookies/youtube_cookies.txt`
  - `cookies/tiktok_cookies.txt`

Do **not** commit these.

---

## 4) First-run workflow (single-channel pilot)

1. Ensure channel account is configured:

```powershell
python accounts\setup_wizard.py market_meltdowns
python accounts\lockdown.py market_meltdowns
```

2. Produce and queue one clip:

```powershell
python -m engine.cli --channel market_meltdowns --count 1 --trend-radar
```

3. Publish queued job:

```powershell
python -u -m publisher.run --platform youtube --channel market_meltdowns
```

4. Confirm `publish_results.post_url` has a real YouTube Shorts URL.

---

## 5) Daily operations commands

### Generate new queued jobs
```powershell
python -m engine.cli --all --count 1 --trend-radar --watchdog --export-status output\ops_status.json
```

### Run publisher for a channel
```powershell
python -u -m publisher.run --platform youtube --channel <channel_name>
```

### Budget/slot view
```powershell
python -m engine.cli --status
```

---

## 6) Agent behavior policy (important)

- Prioritize **publish reliability** over feature work.
- If worker fails: capture screenshot + HTML artifacts from `logs/` and report root cause.
- Only mark success when `post_url` is present.
- Use safety filters by default (do not disable unless explicitly asked).
- Keep Sora lane optional (`--enable-sora-lane` only when requested).

---

## 7) Recommended reminder cadence

Set repeating reminders for the dedicated operator:

- Every 2 hours (active window):
  - Run `engine --status`
  - Check failed jobs + retries
  - Confirm latest posted URL per active channel
- End-of-day:
  - Export status JSON
  - Post short ops recap to Discord

---

## 8) Handoff template (for new OpenClaw session)

Use this as the first instruction in a new dedicated session:

> You are the Clip Empire Ops Agent. Work only in `C:\Users\kanaw\clip-empire`. Your goals are queue health, upload success, and clear Discord reporting. Run engine + publisher safely, keep retries under control, and always include real post URLs in success summaries. Read `docs/OPENCLAW_AGENT_SETUP.md` and `docs/DISCORD_SERVER_BLUEPRINT.md` first.

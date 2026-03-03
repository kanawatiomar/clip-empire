# Discord Launch Message Pack (Day 1)

Copy/paste these directly into your new Clip Empire Discord server channels.

---

## #start-here

```text
👋 Welcome to Clip Empire Ops.

This server runs the 50-account short-form system.

Core flow:
1) Engine: ingest → transform → queue
2) Publisher: browser upload + URL capture
3) Analytics: performance loop + source/template optimization

Start docs:
- OPENCLAW_AGENT_SETUP.md
- DISCORD_SERVER_BLUEPRINT.md
- DISCORD_BOOTSTRAP_CHECKLIST.md
- OPS_RUNBOOK.md

Operational rule:
- Use #incident-room only for active blockers.
- Keep routine logs in #ops-status / #publish-success / #publish-failures.
```

---

## #announcements

```text
🚀 Clip Empire server is now live.

Current stage: controlled rollout.

Phase 1:
- Validate engine + publisher on pilot channels
- Confirm consistent real post_url capture
- Keep failure rate under threshold before scaling

After pilot passes, we’ll ramp channel count and daily volume.
```

---

## #engine-control

```text
⚙️ Engine Control Quick Commands

Status:
python -m engine.cli --status

Single channel pilot:
python -m engine.cli --channel market_meltdowns --count 1 --trend-radar --watchdog --export-status output\ops_status.json

All channels (light run):
python -m engine.cli --all --count 1 --trend-radar --watchdog --export-status output\ops_status.json

Notes:
- Keep policy filter ON by default
- Sora lane is optional: --enable-sora-lane
```

---

## #publisher-control

```text
📤 Publisher Control Quick Commands

Run one channel:
python -u -m publisher.run --platform youtube --channel market_meltdowns

Run another channel:
python -u -m publisher.run --platform youtube --channel crypto_confessions

Success criteria:
- publish_jobs.status = succeeded
- publish_results.post_url contains real YouTube URL
```

---

## #publish-success format

```text
✅ PUBLISH SUCCESS
Channel: <channel_name>
Job: <job_id>
URL: <youtube_url>
Title: <title>
Latency: <duration>
```

---

## #publish-failures format

```text
❌ PUBLISH FAILURE
Channel: <channel_name>
Job: <job_id>
Error Class: <error_class>
Last Error: <short_error>
Retry Plan: <attempt x/3, next retry time>
Artifacts: youtube_fail_<jobid>.png / .html
```

---

## #ops-status format

```text
📊 OPS STATUS SNAPSHOT
Queued: <n>
Running: <n>
Succeeded (24h): <n>
Failed (24h): <n>

Top blockers:
1) <blocker>
2) <blocker>
3) <blocker>

Next action window: <time>
```

---

## #incident-room kickoff template

```text
🚨 INCIDENT OPENED
Severity: <low/med/high>
Started: <timestamp>
Affected channels: <list>
Symptom: <what broke>
Current hypothesis: <root cause guess>
Owner: <name>
Next update ETA: <time>
```

---

## #daily-recap template

```text
🧾 DAILY RECAP
Date: <YYYY-MM-DD>

Uploads queued: <n>
Uploads succeeded: <n>
Uploads failed: <n>
Success rate: <x%>

Top channels by output:
1) <channel> — <n>
2) <channel> — <n>
3) <channel> — <n>

Top issues:
- <issue>
- <issue>

Tomorrow priorities:
1) <priority>
2) <priority>
3) <priority>
```

# Discord Server Blueprint (Clip Empire Ops)

Use this structure for a **new dedicated Clip Empire Discord server**.

---

## 1) Suggested category/channel layout

## 📌 HQ
- `#start-here` — rules + runbook links
- `#announcements` — major changes only
- `#introductions` — who/what this server is for

## 🚦 Ops Control
- `#engine-control` — commands, manual run confirmations
- `#publisher-control` — publish worker actions
- `#ops-status` — periodic status snapshots
- `#incident-room` — active failures only

## 📈 Output Feeds
- `#queued-jobs`
- `#publish-success`
- `#publish-failures`
- `#daily-recap`

## 🧠 Strategy
- `#content-strategy`
- `#source-ideas`
- `#template-ab-tests`
- `#growth-experiments`

## 📊 Analytics
- `#channel-performance`
- `#winner-loser-board`
- `#metrics-dumps`

## 🛠️ Dev
- `#engine-dev`
- `#publisher-dev`
- `#bug-triage`
- `#feature-rollout`

---

## 2) Role model

- `Owner`
- `Ops Lead`
- `Agent` (bot + assistant role)
- `Analyst`
- `Editor`
- `Observer` (read-only)

Minimum permissions for Agent:
- Read/Send in ops/feed/dev channels
- Attach files/screenshots in failure channels
- No admin perms needed

---

## 3) Intro copy (drop into #introductions)

```text
Welcome to Clip Empire Ops.

This server runs the 50-account short-form system:
- Engine: ingest -> transform -> queue
- Publisher: browser-based upload + URL capture
- Analytics: daily performance loops

Use #engine-control and #publisher-control for operational actions.
Use #incident-room only for live failures.
Use #publish-success / #publish-failures for execution visibility.
```

---

## 4) Notification routing rules

### Post to `#publish-success` when:
- job_id succeeded
- real `post_url` exists
- include: channel, title, URL, schedule, run time

### Post to `#publish-failures` when:
- final failure or >2 retries
- include: error class, retry plan, artifact file names

### Post to `#ops-status` every 2–4h:
- queued/running/succeeded/failed counts
- budget remaining by channel
- top 3 blockers

---

## 5) Message format standards

Keep messages short and scannable.

Success format:
```text
✅ PUBLISH SUCCESS
Channel: market_meltdowns
Job: <job_id>
URL: https://youtube.com/shorts/...
Latency: 4m12s
```

Failure format:
```text
❌ PUBLISH FAILURE
Channel: market_meltdowns
Job: <job_id>
Error: upload_timeout
Retry: in 10m (attempt 2/3)
Artifacts: youtube_fail_<jobid>.png/.html
```

---

## 6) Suggested automations

- Cron/heartbeat post to `#ops-status`
- Auto-post success events to `#publish-success`
- Auto-post persistent failures to `#incident-room`
- Daily summary (wins/losses/throughput) to `#daily-recap`

---

## 7) Launch checklist for new server

- [ ] Create categories/channels above
- [ ] Create roles + permissions
- [ ] Pin runbook links in `#start-here`
- [ ] Test one success + one failure post format
- [ ] Confirm bot can attach logs/screenshots
- [ ] Enable alerting only on failure channels (reduce noise)

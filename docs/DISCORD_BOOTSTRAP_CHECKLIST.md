# Discord Bootstrap Checklist (Clip Empire Server)

Use this when creating a fresh Discord server for Clip Empire ops.

---

## 0) Pre-flight

- [ ] Create server name (suggested: `Clip Empire Ops`)
- [ ] Enable Community features (optional but useful for organization)
- [ ] Confirm bot/app is invited with required scopes

---

## 1) Create categories + channels (in this order)

## 📌 HQ
- [ ] `#start-here`
- [ ] `#announcements`
- [ ] `#introductions`

## 🚦 Ops Control
- [ ] `#engine-control`
- [ ] `#publisher-control`
- [ ] `#ops-status`
- [ ] `#incident-room`

## 📈 Output Feeds
- [ ] `#queued-jobs`
- [ ] `#publish-success`
- [ ] `#publish-failures`
- [ ] `#daily-recap`

## 🧠 Strategy
- [ ] `#content-strategy`
- [ ] `#source-ideas`
- [ ] `#template-ab-tests`
- [ ] `#growth-experiments`

## 📊 Analytics
- [ ] `#channel-performance`
- [ ] `#winner-loser-board`
- [ ] `#metrics-dumps`

## 🛠️ Dev
- [ ] `#engine-dev`
- [ ] `#publisher-dev`
- [ ] `#bug-triage`
- [ ] `#feature-rollout`

---

## 2) Create roles

- [ ] `Owner`
- [ ] `Ops Lead`
- [ ] `Agent`
- [ ] `Analyst`
- [ ] `Editor`
- [ ] `Observer`

---

## 3) Apply permissions baseline

### Agent role
- [ ] Read/Send in: ops control + output feeds + dev + analytics
- [ ] Attach files in: `#publish-failures`, `#incident-room`, `#bug-triage`
- [ ] No admin or role-management permissions

### Observer role
- [ ] Read-only everywhere except control channels

### @everyone
- [ ] No write in `#announcements`
- [ ] No write in output-feed channels unless needed

---

## 4) Pin core docs in #start-here

- [ ] `docs/OPENCLAW_AGENT_SETUP.md`
- [ ] `docs/DISCORD_SERVER_BLUEPRINT.md`
- [ ] `docs/OPS_RUNBOOK.md`
- [ ] Link to repo + branch

---

## 5) Post initial server messages

## `#introductions`
```text
Welcome to Clip Empire Ops.

This server runs the 50-account short-form system:
- Engine: ingest -> transform -> queue
- Publisher: browser-based upload + URL capture
- Analytics: daily performance loops

Use #engine-control and #publisher-control for operational actions.
Use #incident-room only for live failures.
```

## `#start-here`
```text
Operational quickstart:
1) Run engine to queue jobs
2) Run publisher worker for target channels
3) Watch publish-success / publish-failures
4) Escalate only persistent failures in incident-room
```

---

## 6) Test routing (mandatory)

- [ ] Send fake success post to `#publish-success`
- [ ] Send fake failure post to `#publish-failures`
- [ ] Send status snapshot to `#ops-status`
- [ ] Verify bot can attach screenshot and HTML in failure channels

---

## 7) Optional channel ID map template

Paste this into your internal notes once channels are created:

```text
HQ
- start-here: <id>
- announcements: <id>
- introductions: <id>

Ops Control
- engine-control: <id>
- publisher-control: <id>
- ops-status: <id>
- incident-room: <id>

Output Feeds
- queued-jobs: <id>
- publish-success: <id>
- publish-failures: <id>
- daily-recap: <id>

Strategy
- content-strategy: <id>
- source-ideas: <id>
- template-ab-tests: <id>
- growth-experiments: <id>

Analytics
- channel-performance: <id>
- winner-loser-board: <id>
- metrics-dumps: <id>

Dev
- engine-dev: <id>
- publisher-dev: <id>
- bug-triage: <id>
- feature-rollout: <id>
```

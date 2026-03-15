# Clip Empire Dashboard

Operational control center for the Clip Empire Shorts pipeline. Real-time monitoring, analytics, and controls for the automated video generation and publishing system.

## ✨ Features (30/30 Complete)

### Core Features (1-5)
1. **Real-Time Health Monitoring** — Live system status, health scores, and component breakdown
2. **Live Queue Management** — View and manage the publish queue with real-time updates
3. **Channel Analytics** — Per-channel performance metrics, revenue tracking, and growth analytics
4. **Top Clips Board** — Highlight best performing clips with engagement metrics and revenue
5. **Daily Summary Reports** — Automated daily summaries with key metrics and trends

### Channel Controls (6-10)
6. **Pause/Resume Channels** — Stop/start publishing for specific channels on demand
7. **Bulk Channel Actions** — Activate, pause, or queue operations across multiple channels
8. **Settings Panel** — Configure channel-specific settings (descriptions, categories, tags)
9. **Channel Status Dashboard** — Real-time status monitoring of all managed channels
10. **Health History Tracking** — Track health score changes and system performance over time

### Data & Analytics (11-15)
11. **Metrics Daily Analytics** — Detailed daily performance metrics and trends
12. **Revenue Breakdown** — Income tracking by channel, content type, and time period
13. **Posting Time Optimization** — Analytics for best posting times based on historical data
14. **Title Performance Scoring** — A/B analysis of title effectiveness and patterns
15. **Style Performance Metrics** — Content style analysis with engagement correlations

### Publishing Controls (16-20)
16. **Process Queue** — Trigger one-pass queue processing for video publishing
17. **Start Engine Scan** — Launch full engine scan for new content detection
18. **Refresh Data** — Force regenerate dashboard data from source database
19. **Render Cleanup** — Manage and cleanup video render artifacts with confirmation
20. **Error Logging & Diagnostics** — View detailed logs and error summaries from the system

### UI/UX Features (21-25)
21. **Dark/Light/High-Contrast Themes** — Three professional color schemes with smooth transitions
22. **Responsive Design** — Full mobile, tablet, and desktop support
23. **Notification Center** — Real-time alerts and system notifications with read tracking
24. **Live Scheduled Posts** — View upcoming scheduled posts for the next 7 days
25. **Toast Notifications** — Non-intrusive feedback for user actions and system events

### Advanced Features (26-30)
26. **API-Driven Controls** — Optional local API server for live actions on the machine
27. **Static Mode (Read-Only)** — GitHub Pages ready, auto-refreshing data without API
28. **Theme Persistence** — User theme preference saved to browser localStorage
29. **Print-Friendly Dashboard** — Optimized PDF export with clean print stylesheet
30. **Export & Deploy** — Export as PDF/JSON, copy dashboard URL, GitHub Pages workflow

## 📋 What It Includes

- **`index.html`** — Responsive dashboard UI with all 30 features
- **`generate_data.py`** — Standalone SQLite → JSON exporter (read-only mode)
- **`control_api.py`** — Optional local server/API for real-time controls
- **`data.json`** — Generated dashboard payload (auto-refreshed)
- **`.github/workflows/deploy-dashboard.yml`** — GitHub Pages auto-deploy on push

## 📊 Data Sources

The dashboard reads from the Clip Empire database:

- `channels` — Channel metadata and status
- `publish_jobs` — Publishing task queue and history
- `publish_results` — Publishing outcomes and metrics
- `clip_assets` — Generated clip metadata
- `metrics_daily` — Daily performance analytics
- `platform_variants` — Content variants for fallback stats
- `source_clips` — Source content library

## 🚀 Quick Start

### Static Mode (GitHub Pages Friendly)

Perfect for read-only monitoring or GitHub Pages deployment:

```powershell
cd C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire

# Generate dashboard data from SQLite
py -3 dashboard/generate_data.py

# Data is now in dashboard/data.json
# Open dashboard/index.html in your browser (auto-refreshes data every 15 seconds)
```

Then publish the `dashboard/` folder to any static host (GitHub Pages, Netlify, etc).

### Local Control Mode

For live controls and real-time actions on the machine:

```powershell
cd C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire

# In one terminal: Run the control API server
py -3 dashboard/control_api.py

# In another terminal: Open in browser
start http://127.0.0.1:8787/
```

**Available Live Controls:**
- ▶️ Start Engine Scan — Run `py -3 -m engine.cli --all`
- 📤 Process Queue — Execute one `publisher.youtube_worker.run_once(...)` pass
- ⏸️ Pause/Resume Channel — Update `channels.status` in database
- 📋 View Logs — Returns latest DB error summaries and diagnostics
- 🔄 Refresh Data — Regenerate `dashboard/data.json` on demand

## 📦 Exporting Data

The dashboard includes built-in export tools (Feature #30):

**PDF Export:**
- Click "📄 PDF" button in header
- Browser print dialog opens with print-optimized styling
- Save as PDF for reports and archival

**JSON Export:**
- Click "📋 JSON" button in header
- Downloads current `data.json` with timestamp
- Useful for data analysis, backups, or external integrations

**Copy Dashboard URL:**
- Click "🔗 Copy URL" button in header
- Copies current dashboard URL to clipboard for sharing

## 🌐 GitHub Pages Deployment

The repo includes an automated deployment workflow:

**Prerequisites:**
1. Repo must have GitHub Pages enabled on `gh-pages` branch
2. Go to repo settings → Pages → Source: `Deploy from a branch` → `gh-pages`

**Workflow Details:**
- Triggered automatically on push to `master`
- Runs `generate_data.py` to refresh data
- Deploys `dashboard/` folder to GitHub Pages
- Status page: `https://github.com/<user>/<repo>/deployments`

**Manual Trigger:**
```powershell
# Push to master to trigger
git add dashboard/
git commit -m "Update dashboard"
git push origin master

# Or manually trigger in GitHub Actions UI
```

**View Live Dashboard:**
```
https://<github-username>.github.io/<repo>/
```

## 🎨 Themes & Customization

**Built-in Themes:**
- 🌙 Dark (default) — Low-light war room aesthetic
- ☀️ Light — Professional daytime theme
- ✨ High Contrast — Accessibility-optimized

**Theme Switching:**
- Use dropdown in dashboard header
- Selection saved to browser localStorage
- Smooth transitions between themes

**Dark Mode CSS Variables:**
```css
--bg: #0a0e17           /* Main background */
--surface: #12172b      /* Card surfaces */
--gold: #c9a84c         /* Accent color */
--text: #e8eaf0         /* Text color */
--success: #3dd68c       /* Success state */
--error: #e85454         /* Error state */
--warning: #e8b04e       /* Warning state */
```

## 🛠️ Technical Details

### Database Read-Only Safety

`generate_data.py` opens the SQLite database in **read-only mode** (`open(db_path, 'r')` equivalent through `PRAGMA query_only`):
- No risk of data corruption
- Can run while engine and publisher are active
- Safe for automated scheduling

### Auto-Refresh Behavior

- Dashboard auto-fetches `data.json` every 15 seconds (configurable via `meta.refresh_seconds`)
- No external API calls required in static mode
- Configurable refresh interval in `generate_data.py` output

### Current Database State

- `metrics_daily` — Sparse data (limited historical metrics)
- `clip_assets` — Empty (no clip metadata)
- `publish_jobs` — Full queue history
- Fallback to `platform_variants` + `source_clips` for analytics when metrics unavailable

## 🔧 Monitoring & Maintenance

### Regular Updates

```powershell
# Update data (manual)
py -3 dashboard/generate_data.py

# Or schedule with Windows Task Scheduler / cron
# Example: Every 10 minutes
# See: .github/workflows/update-dashboard.yml for GitHub Actions version
```

### Performance Considerations

- `data.json` size: ~340KB (loaded fresh every 15s)
- Dashboard uses ~5-10MB memory in browser
- Renders 1000+ data points with smooth animations
- Optimized for Chrome, Safari, Edge (modern browsers)

### Debugging

**Check data freshness:**
```powershell
(Get-Item dashboard/data.json).LastWriteTime
```

**Verify data generation:**
```powershell
py -3 dashboard/generate_data.py --verbose
```

**Test API server:**
```powershell
curl http://127.0.0.1:8787/api/health
```

## 📖 Feature Breakdown by Category

### Monitoring & Analytics (15 features)
- Health monitoring, queue management, channel analytics
- Top clips board, daily summaries
- Revenue tracking, posting time optimization
- Title/style performance analysis
- Health history and diagnostic logs

### Controls & Automation (8 features)
- Pause/resume channels, bulk actions
- Settings panel, engine control
- Queue processing, render cleanup
- Data refresh and diagnostics

### UI & Experience (5 features)
- Three professional themes
- Mobile-responsive design
- Notification center with read tracking
- Scheduled posts timeline
- Toast feedback system

### Export & Integration (2 features)
- PDF export with print-friendly styling
- JSON data export for analysis
- Shareable dashboard URL

## 🚨 Notes & Caveats

- Dashboard is **read-only by default** in static mode
- Control buttons require `control_api.py` running locally
- GitHub Pages shows read-only monitoring dashboard
- Print CSS optimized for Chrome/Edge (Firefox may vary)
- Dark backgrounds removed in print to save toner
- Mobile: Swipe to see more details, landscape for full view

## 📝 Git Workflow

```powershell
# After making changes
git add dashboard/
git commit -m "feat: <description> (Feature #XX)"
git push origin master

# Workflow auto-triggers GitHub Pages deployment
# Check status: https://github.com/<user>/<repo>/actions
```

## 🎯 What's Next

The dashboard is feature-complete with 30 features. Future enhancements could include:
- Real-time WebSocket updates instead of polling
- Database write operations (schedule posts, update settings)
- Advanced analytics (ML-based recommendations)
- Custom report generation
- API key management and security improvements

---

**Built by Omar's Clip Empire Team**  
**Latest Update:** Feature #30 - Dashboard Export & GitHub Pages Deploy  
**Status:** Production Ready ✅

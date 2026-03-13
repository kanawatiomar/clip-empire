# Clip Empire Dashboard

Operational control center for the Clip Empire Shorts pipeline.

## What it ships with

- `index.html` — responsive dashboard UI
- `generate_data.py` — standalone read-only SQLite → `data.json` exporter
- `control_api.py` — optional local server/API for real control buttons
- `data.json` — generated dashboard payload

## Data sources

The dashboard reads from:

- `channels`
- `publish_jobs`
- `publish_results`
- `clip_assets`
- `metrics_daily`
- fallback proxy data from `platform_variants` + `source_clips` when metrics are sparse

## Static mode (GitHub Pages friendly)

From repo root:

```powershell
py -3 dashboard/generate_data.py
```

Then publish the `dashboard/` folder. The page auto-refreshes `data.json` every 15 seconds.

## Local control mode

If you want the buttons to actually run actions on the machine:

```powershell
cd C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire
py -3 dashboard/control_api.py
```

Open:

- `http://127.0.0.1:8787/`

Available actions:

- Start Engine Scan → `py -3 -m engine.cli --all`
- Process Queue → runs one `publisher.youtube_worker.run_once(...)` pass
- Pause / Resume channel → updates `channels.status`
- View Logs → returns latest DB error summaries
- Refresh Data → regenerates `dashboard/data.json`

## Notes

- `generate_data.py` opens SQLite in **read-only mode**.
- The current DB has sparse `metrics_daily` and empty `clip_assets`, so the Top Clips board falls back to source clip proxy stats when needed.
- GitHub Pages works as a read-only monitor. For live controls, use `control_api.py` locally.

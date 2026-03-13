#!/usr/bin/env python3
"""Generate dashboard/data.json for the Clip Empire control center.

Reads clip_empire.db in read-only mode and emits a static JSON payload suitable
for GitHub Pages or a lightweight local HTTP server.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
DB_PATH = REPO_ROOT / 'data' / 'clip_empire.db'
OUTPUT_FILE = BASE_DIR / 'data.json'

RPM_PER_1K_VIEWS = 0.85
REFRESH_SECONDS = 15


def utc_now() -> datetime:
    return datetime.utcnow()


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def fmt_compact_dt(value: str | None) -> str | None:
    dt = parse_dt(value)
    if not dt:
        return value
    return dt.strftime('%Y-%m-%d %H:%M')


def rel_time(value: str | None) -> str:
    dt = parse_dt(value)
    if not dt:
        return '—'
    diff = utc_now() - dt
    seconds = max(int(diff.total_seconds()), 0)
    if seconds < 60:
        return 'now'
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def normalize_status(status: str | None) -> str:
    raw = (status or 'unknown').lower()
    if raw in {'running', 'processing'}:
        return 'running'
    if raw in {'queued', 'succeeded', 'failed', 'cancelled', 'paused'}:
        return raw
    return raw


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f'Database not found: {DB_PATH}')
    uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def query_all(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, params).fetchall()


def query_one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row:
    return conn.execute(sql, params).fetchone()


def load_channel_view_metrics(conn: sqlite3.Connection) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    rows = query_all(
        conn,
        """
        SELECT channel_name,
               COALESCE(AVG(NULLIF(views_median, 0)), 0) AS avg_views_14d,
               COALESCE(SUM(NULLIF(views_total, 0)), 0) AS views_total_14d,
               COALESCE(SUM(NULLIF(likes_total, 0)), 0) AS likes_total_14d
        FROM metrics_daily
        WHERE platform = 'youtube' AND date >= date('now', '-14 day')
        GROUP BY channel_name
        """,
    )
    for row in rows:
        metrics[row['channel_name']] = {
            'avg_views': float(row['avg_views_14d'] or 0),
            'views_total_14d': float(row['views_total_14d'] or 0),
            'likes_total_14d': float(row['likes_total_14d'] or 0),
            'source': 'metrics_daily',
        }

    fallback_rows = query_all(
        conn,
        """
        SELECT channel_name,
               COALESCE(AVG(NULLIF(view_count, 0)), 0) AS avg_source_views,
               COALESCE(MAX(NULLIF(view_count, 0)), 0) AS max_source_views
        FROM source_clips
        WHERE used_at >= datetime('now', '-14 day')
        GROUP BY channel_name
        """,
    )
    for row in fallback_rows:
        channel = row['channel_name']
        if channel not in metrics or metrics[channel]['avg_views'] <= 0:
            metrics[channel] = {
                'avg_views': float(row['avg_source_views'] or 0),
                'views_total_14d': 0.0,
                'likes_total_14d': 0.0,
                'source': 'source_clips_proxy',
                'max_source_views': float(row['max_source_views'] or 0),
            }
    return metrics


def get_live_status(conn: sqlite3.Connection) -> dict[str, Any]:
    active_channels = int(query_one(conn, "SELECT COUNT(*) AS c FROM channels WHERE status='active'")['c'])

    today = utc_now().strftime('%Y-%m-%d')
    job_rows = query_all(
        conn,
        "SELECT status, COUNT(*) AS c FROM publish_jobs WHERE date(created_at)=? GROUP BY status",
        (today,),
    )
    status_counts = Counter()
    for row in job_rows:
        status_counts[normalize_status(row['status'])] += int(row['c'] or 0)

    render_queue_depth = int(
        query_one(
            conn,
            "SELECT COUNT(*) AS c FROM publish_jobs WHERE status IN ('queued','running','processing')",
        )['c']
    )
    total_channels = int(query_one(conn, "SELECT COUNT(*) AS c FROM channels")['c'])
    jobs_total = sum(status_counts.values())
    return {
        'active_channels': active_channels,
        'total_channels': total_channels,
        'jobs_today': {
            'total': jobs_total,
            'queued': status_counts.get('queued', 0),
            'running': status_counts.get('running', 0),
            'succeeded': status_counts.get('succeeded', 0),
            'failed': status_counts.get('failed', 0),
            'cancelled': status_counts.get('cancelled', 0),
        },
        'render_queue_depth': render_queue_depth,
        'last_updated': utc_now().isoformat() + 'Z',
    }


def get_queue_monitor(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = query_all(
        conn,
        """
        SELECT pj.job_id, pj.channel_name, pj.status, pj.attempts, pj.created_at,
               pj.updated_at, pj.schedule_at, pj.last_error, pr.post_url
        FROM publish_jobs pj
        LEFT JOIN (
            SELECT job_id, MAX(finished_at) AS latest_finished, MAX(post_url) AS post_url
            FROM publish_results
            GROUP BY job_id
        ) pr ON pr.job_id = pj.job_id
        ORDER BY datetime(COALESCE(pj.updated_at, pj.created_at)) DESC
        LIMIT 100
        """,
    )
    items = []
    for row in rows:
        items.append({
            'job_id': row['job_id'],
            'job_id_short': (row['job_id'] or '')[:8],
            'channel': row['channel_name'],
            'status': normalize_status(row['status']),
            'attempt': int(row['attempts'] or 0),
            'created_at': row['created_at'],
            'created_at_display': fmt_compact_dt(row['created_at']),
            'created_ago': rel_time(row['created_at']),
            'updated_at': row['updated_at'],
            'scheduled_for': fmt_compact_dt(row['schedule_at']),
            'error': row['last_error'],
            'has_error': bool(row['last_error']),
            'post_url': row['post_url'],
        })
    return items


def get_channel_performance(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    metric_map = load_channel_view_metrics(conn)
    channel_rows = query_all(conn, "SELECT channel_name, category, status, daily_target FROM channels ORDER BY channel_name")
    perf: list[dict[str, Any]] = []
    cutoff_24h = (utc_now() - timedelta(hours=24)).isoformat()

    for row in channel_rows:
        channel = row['channel_name']
        published_24h = int(
            query_one(
                conn,
                """
                SELECT COUNT(*) AS c
                FROM publish_jobs
                WHERE channel_name = ?
                  AND status = 'succeeded'
                  AND datetime(COALESCE(updated_at, created_at)) >= datetime(?)
                """,
                (channel, cutoff_24h),
            )['c']
        )
        queued = int(query_one(conn, "SELECT COUNT(*) AS c FROM publish_jobs WHERE channel_name=? AND status='queued'", (channel,))['c'])
        running = int(query_one(conn, "SELECT COUNT(*) AS c FROM publish_jobs WHERE channel_name=? AND status IN ('running','processing')", (channel,))['c'])
        failed_7d = int(
            query_one(
                conn,
                """
                SELECT COUNT(*) AS c FROM publish_jobs
                WHERE channel_name=? AND status='failed'
                  AND datetime(COALESCE(updated_at, created_at)) >= datetime('now', '-7 day')
                """,
                (channel,),
            )['c']
        )
        latest_upload = query_one(
            conn,
            """
            SELECT pr.post_url, pj.caption_text, pj.updated_at
            FROM publish_jobs pj
            LEFT JOIN publish_results pr ON pr.job_id = pj.job_id
            WHERE pj.channel_name=? AND pj.status='succeeded'
            ORDER BY datetime(COALESCE(pj.updated_at, pj.created_at)) DESC
            LIMIT 1
            """,
            (channel,),
        )
        metrics = metric_map.get(channel, {'avg_views': 0.0, 'views_total_14d': 0.0, 'likes_total_14d': 0.0, 'source': 'none'})
        avg_views = float(metrics.get('avg_views') or 0)
        rpm = round((avg_views / 1000.0) * RPM_PER_1K_VIEWS, 2) if avg_views else 0.0
        target = int(row['daily_target'] or 0)
        deficit = max(target - published_24h, 0)
        completion = round((published_24h / target) * 100, 1) if target else 0.0
        lagging = row['status'] == 'active' and published_24h < target
        perf.append({
            'channel': channel,
            'status': row['status'],
            'category': row['category'],
            'target_per_day': target,
            'published_24h': published_24h,
            'queue_depth': queued,
            'running_jobs': running,
            'failed_7d': failed_7d,
            'avg_views': round(avg_views),
            'rpm': rpm,
            'deficit': deficit,
            'completion_rate': completion,
            'lagging': lagging,
            'views_source': metrics.get('source', 'none'),
            'latest_title': (latest_upload['caption_text'] if latest_upload else None),
            'latest_url': (latest_upload['post_url'] if latest_upload else None),
            'latest_uploaded_at': fmt_compact_dt(latest_upload['updated_at']) if latest_upload and latest_upload['updated_at'] else None,
        })

    perf.sort(key=lambda item: (not item['lagging'], item['deficit'], item['avg_views'] * -1, item['channel']))
    return perf


def get_top_clips(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = query_all(
        conn,
        """
        SELECT pj.job_id, pj.channel_name, pj.caption_text, pj.updated_at, pr.post_url,
               pv.clip_id, sc.title AS source_title, sc.creator, sc.view_count
        FROM publish_jobs pj
        LEFT JOIN publish_results pr ON pr.job_id = pj.job_id
        LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
        LEFT JOIN source_clips sc ON sc.clip_id = pv.clip_id
        WHERE pj.status='succeeded'
          AND datetime(COALESCE(pj.updated_at, pj.created_at)) >= datetime('now', '-7 day')
        ORDER BY COALESCE(sc.view_count, 0) DESC, datetime(COALESCE(pj.updated_at, pj.created_at)) DESC
        LIMIT 20
        """,
    )
    clips = []
    for row in rows:
        views = int(row['view_count'] or 0)
        likes = None
        ctr = None
        clips.append({
            'clip_id': row['clip_id'] or row['job_id'],
            'clip_id_short': (row['clip_id'] or row['job_id'] or '')[:12],
            'title': row['caption_text'] or row['source_title'] or 'Untitled clip',
            'source_title': row['source_title'],
            'creator': row['creator'],
            'channel': row['channel_name'],
            'views': views,
            'likes': likes,
            'ctr_percent': ctr,
            'upload_date': fmt_compact_dt(row['updated_at']),
            'youtube_url': row['post_url'],
            'metric_mode': 'source_clip_proxy' if views else 'unavailable',
        })
    return clips


def get_recent_uploads(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = query_all(
        conn,
        """
        SELECT pj.job_id, pj.channel_name, pj.status, pj.updated_at, pj.caption_text, pj.last_error,
               pr.post_url
        FROM publish_jobs pj
        LEFT JOIN publish_results pr ON pr.job_id = pj.job_id
        ORDER BY datetime(COALESCE(pj.updated_at, pj.created_at)) DESC
        LIMIT 10
        """,
    )
    items = []
    for row in rows:
        items.append({
            'job_id': row['job_id'],
            'job_id_short': (row['job_id'] or '')[:8],
            'channel': row['channel_name'],
            'status': normalize_status(row['status']),
            'updated_at': row['updated_at'],
            'updated_at_display': fmt_compact_dt(row['updated_at']),
            'updated_ago': rel_time(row['updated_at']),
            'title': row['caption_text'],
            'url': row['post_url'],
            'error': row['last_error'],
        })
    return items


def get_logs_preview(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = query_all(
        conn,
        """
        SELECT channel_name, job_id, updated_at, last_error
        FROM publish_jobs
        WHERE last_error IS NOT NULL AND TRIM(last_error) != ''
        ORDER BY datetime(COALESCE(updated_at, created_at)) DESC
        LIMIT 8
        """,
    )
    return [
        {
            'channel': row['channel_name'],
            'job_id_short': row['job_id'][:8],
            'updated_at': fmt_compact_dt(row['updated_at']),
            'message': (row['last_error'] or '').strip()[:240],
        }
        for row in rows
    ]


def get_controls_metadata(conn: sqlite3.Connection) -> dict[str, Any]:
    channels = query_all(conn, "SELECT channel_name, status FROM channels ORDER BY channel_name")
    return {
        'refresh_seconds': REFRESH_SECONDS,
        'local_api_hint': 'Run py -3 dashboard/control_api.py from repo root for live control buttons.',
        'channels': [{'channel': row['channel_name'], 'status': row['status']} for row in channels],
        'actions': [
            {'id': 'engine_scan', 'label': 'Start Engine Scan'},
            {'id': 'process_queue', 'label': 'Process Queue'},
            {'id': 'refresh_data', 'label': 'Refresh Dashboard Data'},
            {'id': 'view_logs', 'label': 'View Logs'},
        ],
    }


def build_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    queue_monitor = get_queue_monitor(conn)
    channel_performance = get_channel_performance(conn)
    lagging = [item for item in channel_performance if item['lagging']]
    payload = {
        'generated_at': utc_now().isoformat() + 'Z',
        'repo_root': str(REPO_ROOT),
        'database_path': str(DB_PATH),
        'live_status': get_live_status(conn),
        'queue_monitor': queue_monitor,
        'channel_performance': channel_performance,
        'top_clips': get_top_clips(conn),
        'recent_uploads': get_recent_uploads(conn),
        'logs_preview': get_logs_preview(conn),
        'controls': get_controls_metadata(conn),
        'insights': {
            'lagging_channels': lagging[:6],
            'lagging_count': len(lagging),
            'queue_backlog': sum(1 for row in queue_monitor if row['status'] in {'queued', 'running'}),
        },
        'meta': {
            'refresh_seconds': REFRESH_SECONDS,
            'channel_count': int(query_one(conn, "SELECT COUNT(*) AS c FROM channels")['c']),
            'job_count': int(query_one(conn, "SELECT COUNT(*) AS c FROM publish_jobs")['c']),
            'has_metrics_daily': int(query_one(conn, "SELECT COUNT(*) AS c FROM metrics_daily")['c']) > 0,
            'has_clip_assets': int(query_one(conn, "SELECT COUNT(*) AS c FROM clip_assets")['c']) > 0,
            'note': 'This DB currently has sparse metrics_daily/clip_assets data, so some leaderboard stats use source clip proxy values.',
        },
    }
    return payload


def main() -> int:
    conn = connect()
    try:
        payload = build_payload(conn)
    finally:
        conn.close()

    OUTPUT_FILE.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(f'Wrote {OUTPUT_FILE}')
    print(f"Active channels: {payload['live_status']['active_channels']} / {payload['live_status']['total_channels']}")
    print(f"Queue backlog: {payload['insights']['queue_backlog']}")
    print(f"Lagging channels: {payload['insights']['lagging_count']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

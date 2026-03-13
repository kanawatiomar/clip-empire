#!/usr/bin/env python3
"""Generate dashboard/data.json for the Clip Empire control center.

Reads clip_empire.db in read-only mode and emits a static JSON payload suitable
for GitHub Pages or a lightweight local HTTP server.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.config.sources import CHANNEL_SOURCES, SOURCE_DEFAULTS

DB_PATH = REPO_ROOT / 'data' / 'clip_empire.db'
OUTPUT_FILE = BASE_DIR / 'data.json'

RPM_PER_1K_VIEWS = 0.85
REFRESH_SECONDS = 30
TREND_DAYS = 30
TREND_LOOKBACK_DAYS = 60
CONTROL_API_BASE = 'http://127.0.0.1:8787'
DISCORD_FEED_LIMIT = 5


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


def trend_direction(current_avg: float, previous_avg: float, tolerance: float = 0.01) -> str:
    if current_avg > previous_avg + tolerance:
        return 'up'
    if current_avg < previous_avg - tolerance:
        return 'down'
    return 'flat'


def calc_window_stats(values: list[float], window: int) -> dict[str, Any]:
    recent = values[-window:] if values else []
    previous = values[-(window * 2):-window] if len(values) > window else []
    current_avg = round(sum(recent) / len(recent), 2) if recent else 0.0
    previous_avg = round(sum(previous) / len(previous), 2) if previous else 0.0
    if not previous and len(recent) >= 2:
        previous_avg = round(sum(recent[:-1]) / max(len(recent) - 1, 1), 2)
    delta = round(current_avg - previous_avg, 2)
    delta_pct = round((delta / previous_avg) * 100, 1) if previous_avg else None
    return {
        'window_days': window,
        'avg': current_avg,
        'previous_avg': previous_avg,
        'delta': delta,
        'delta_pct': delta_pct,
        'direction': trend_direction(current_avg, previous_avg),
        'points': len(recent),
    }


def load_channel_trends(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = query_all(
        conn,
        """
        SELECT channel_name,
               date,
               COALESCE(NULLIF(views_median, 0), CASE WHEN posts > 0 THEN CAST(views_total AS REAL) / posts ELSE 0 END, 0) AS daily_views,
               'metrics_daily' AS source
        FROM metrics_daily
        WHERE platform = 'youtube'
          AND date >= date('now', '-60 day')
        ORDER BY channel_name, date
        """,
    )

    channel_points: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        channel = row['channel_name']
        day = row['date']
        views = float(row['daily_views'] or 0)
        channel_points[channel][day] = {
            'date': day,
            'views': round(views, 2),
            'rpm': round((views / 1000.0) * RPM_PER_1K_VIEWS, 4),
            'source': row['source'],
        }

    fallback_rows = query_all(
        conn,
        """
        SELECT channel_name,
               date(used_at) AS date,
               COALESCE(AVG(NULLIF(view_count, 0)), 0) AS daily_views,
               'source_clips_proxy' AS source
        FROM source_clips
        WHERE used_at IS NOT NULL
          AND date(used_at) >= date('now', '-60 day')
        GROUP BY channel_name, date(used_at)
        ORDER BY channel_name, date(used_at)
        """,
    )
    for row in fallback_rows:
        channel = row['channel_name']
        day = row['date']
        if not channel or not day or day in channel_points[channel]:
            continue
        views = float(row['daily_views'] or 0)
        channel_points[channel][day] = {
            'date': day,
            'views': round(views, 2),
            'rpm': round((views / 1000.0) * RPM_PER_1K_VIEWS, 4),
            'source': row['source'],
        }

    trend_rows: list[dict[str, Any]] = []
    end_day = utc_now().date()
    day_range = [(end_day - timedelta(days=offset)).isoformat() for offset in range(TREND_DAYS - 1, -1, -1)]

    for channel, series_map in sorted(channel_points.items()):
        ordered_days = sorted(series_map)
        if not ordered_days:
            continue
        views_series = [float(series_map[day]['views']) for day in ordered_days]
        rpm_series = [float(series_map[day]['rpm']) for day in ordered_days]
        recent_series = []
        for day in day_range:
            point = series_map.get(day)
            recent_series.append({
                'date': day,
                'views': round(float(point['views']), 2) if point else None,
                'rpm': round(float(point['rpm']), 4) if point else None,
            })

        primary_source = 'metrics_daily' if any(point['source'] == 'metrics_daily' for point in series_map.values()) else 'source_clips_proxy'
        trend_rows.append({
            'channel': channel,
            'source': primary_source,
            'views': {
                'series_30d': recent_series,
                'window_7d': calc_window_stats(views_series, 7),
                'window_30d': calc_window_stats(views_series, 30),
                'latest': round(views_series[-1], 2) if views_series else 0.0,
            },
            'rpm': {
                'series_30d': recent_series,
                'window_7d': calc_window_stats(rpm_series, 7),
                'window_30d': calc_window_stats(rpm_series, 30),
                'latest': round(rpm_series[-1], 4) if rpm_series else 0.0,
            },
        })

    return trend_rows


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


def get_queue_status(conn: sqlite3.Connection) -> dict[str, Any]:
    """Get detailed queue status grouped by job status for Queue Manager.
    
    Returns per-job details including title, retry count, and error messages,
    grouped by status with summary counts.
    """
    rows = query_all(
        conn,
        """
        SELECT job_id, channel_name, caption_text, status, created_at, 
               COALESCE(attempts, 0) AS retry_count, last_error
        FROM publish_jobs
        WHERE status IN ('pending', 'processing', 'failed', 'retrying')
        ORDER BY status, datetime(created_at) DESC
        """,
    )
    
    # Group by status
    grouped: dict[str, list[dict[str, Any]]] = {
        'pending': [],
        'processing': [],
        'failed': [],
        'retrying': [],
    }
    
    for row in rows:
        status = normalize_status(row['status'])
        if status not in grouped:
            grouped[status] = []
        
        # Truncate title to 60 chars and error to 100 chars
        title = (row['caption_text'] or '')[:60]
        error = (row['last_error'] or '')[:100]
        
        job_item = {
            'job_id': row['job_id'],
            'job_id_short': (row['job_id'] or '')[:8],
            'channel': row['channel_name'],
            'title': title or '(untitled)',
            'status': status,
            'created_at': row['created_at'],
            'created_at_display': fmt_compact_dt(row['created_at']),
            'created_ago': rel_time(row['created_at']),
            'retry_count': int(row['retry_count'] or 0),
            'last_error': error,
            'has_error': bool(error),
        }
        grouped[status].append(job_item)
    
    # Build summary
    return {
        'jobs_by_status': grouped,
        'summary': {
            'pending': len(grouped['pending']),
            'processing': len(grouped['processing']),
            'failed': len(grouped['failed']),
            'retrying': len(grouped['retrying']),
            'total': sum(len(v) for v in grouped.values()),
        },
    }


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


def get_recent_clips(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Get the last 10 succeeded publish jobs with thumbnail paths for the preview grid."""
    rows = query_all(
        conn,
        """
        SELECT pj.job_id, pj.channel_name, pj.caption_text, pj.updated_at,
               pr.post_url, pv.clip_id
        FROM publish_jobs pj
        LEFT JOIN publish_results pr ON pr.job_id = pj.job_id
        LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
        WHERE pj.status='succeeded'
        ORDER BY datetime(COALESCE(pj.updated_at, pj.created_at)) DESC
        LIMIT 10
        """,
    )
    items = []
    for row in rows:
        channel = row['channel_name']
        clip_id = row['clip_id']
        
        # Build thumbnail path: renders/thumbnails/{channel}/{clip_id}.jpg
        thumbnail_path = None
        if channel and clip_id:
            thumb_file = REPO_ROOT / 'renders' / 'thumbnails' / channel / f'{clip_id}.jpg'
            if thumb_file.exists():
                # Return relative path for serving via control_api
                thumbnail_path = f'/thumbnails/{channel}/{clip_id}.jpg'
        
        # Truncate title to 60 chars
        title = row['caption_text'] or 'Untitled clip'
        title_truncated = (title[:60] + '...') if len(title) > 60 else title
        
        items.append({
            'job_id': row['job_id'],
            'job_id_short': (row['job_id'] or '')[:8],
            'channel': channel,
            'title': title,
            'title_truncated': title_truncated,
            'thumbnail_path': thumbnail_path,
            'post_url': row['post_url'],
            'published_at': row['updated_at'],
            'published_at_display': fmt_compact_dt(row['updated_at']),
            'published_ago': rel_time(row['updated_at']),
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


def classify_error(error_message: str | None) -> str:
    cleaned = ' '.join((error_message or '').strip().split())
    return cleaned[:50] if cleaned else 'Unknown error'


def get_error_suggestion(error_type: str, count: int) -> str:
    normalized = (error_type or '').lower()
    if 'encoding error' in normalized and count >= 3:
        return 'Check ffmpeg codec settings'
    if 'timeout' in normalized:
        return 'Increase timeout threshold or check network'
    if 'quota exceeded' in normalized:
        return 'Check YouTube API quota usage'
    return 'Review logs for context'


def get_error_analysis(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = query_all(
        conn,
        """
        SELECT last_error,
               created_at,
               updated_at,
               DATE(COALESCE(updated_at, created_at)) AS error_date,
               DATETIME(COALESCE(updated_at, created_at)) AS occurred_at
        FROM publish_jobs
        WHERE last_error IS NOT NULL
          AND TRIM(last_error) != ''
        ORDER BY DATETIME(COALESCE(updated_at, created_at)) DESC
        """,
    )

    grouped: dict[str, dict[str, Any]] = {}
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    for row in rows:
        error_type = classify_error(row['last_error'])
        bucket = grouped.setdefault(
            error_type,
            {
                'error_type': error_type,
                'count': 0,
                'last_seen': None,
                'trend': {'today': 0, 'yesterday': 0, 'week_ago': 0},
            },
        )
        bucket['count'] += 1

        occurred_at = row['occurred_at']
        if occurred_at and (not bucket['last_seen'] or occurred_at > bucket['last_seen']):
            bucket['last_seen'] = occurred_at

        error_day = parse_dt(row['error_date'])
        if error_day:
            day = error_day.date()
            if day == today:
                bucket['trend']['today'] += 1
            if day == yesterday:
                bucket['trend']['yesterday'] += 1
            if day == week_ago:
                bucket['trend']['week_ago'] += 1

    ranked = sorted(grouped.values(), key=lambda item: (-item['count'], item['error_type']))[:5]
    top_count = ranked[0]['count'] if ranked else 0

    items: list[dict[str, Any]] = []
    for item in ranked:
        count = int(item['count'])
        severity = 'critical' if top_count and count == top_count else 'warning' if count > 1 else 'info'
        items.append({
            'error_type': item['error_type'],
            'count': count,
            'trend': item['trend'],
            'last_seen': item['last_seen'],
            'last_seen_display': fmt_compact_dt(item['last_seen']),
            'suggestion': get_error_suggestion(item['error_type'], count),
            'severity': severity,
        })

    return {
        'top_errors': items,
        'total_errors': sum(int(item['count']) for item in grouped.values()),
        'distinct_errors': len(grouped),
        'log_viewer_label': 'View Full Logs',
        'log_viewer_target': 'logs_dialog',
    }


def get_source_health(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    source_rows = query_all(
        conn,
        """
        SELECT source_id, type, url, ingested_at
        FROM sources
        """,
    )
    health_rows = query_all(
        conn,
        """
        SELECT source_key, success_count, failure_count, last_error, updated_at
        FROM source_health
        """,
    )
    recent_clip_rows = query_all(
        conn,
        """
        SELECT source_url, COUNT(*) AS clips_24h
        FROM source_clips
        WHERE datetime(used_at) >= datetime('now', '-24 hour')
        GROUP BY source_url
        """,
    )

    source_map: dict[str, dict[str, Any]] = {}
    for row in source_rows:
        key = row['url'] or row['source_id']
        if not key:
            continue
        source_map[key] = {
            'source_id': row['source_id'] or key,
            'platform': row['type'] or 'unknown',
            'last_fetch': row['ingested_at'],
            'success_count': 0,
            'failure_count': 0,
            'last_error': None,
        }

    for row in health_rows:
        key = row['source_key']
        item = source_map.get(key, {
            'source_id': key,
            'platform': 'unknown',
            'last_fetch': row['updated_at'],
            'success_count': 0,
            'failure_count': 0,
            'last_error': row['last_error'],
        })
        if item.get('platform') == 'unknown':
            lowered = (key or '').lower()
            if 'tiktok.com' in lowered:
                item['platform'] = 'tiktok'
            elif 'youtube.com' in lowered or 'youtu.be' in lowered:
                item['platform'] = 'youtube'
        item['last_fetch'] = row['updated_at'] or item.get('last_fetch')
        item['success_count'] = int(row['success_count'] or 0)
        item['failure_count'] = int(row['failure_count'] or 0)
        item['last_error'] = row['last_error']
        source_map[key] = item

    recent_clips = {row['source_url']: int(row['clips_24h'] or 0) for row in recent_clip_rows}
    items: list[dict[str, Any]] = []
    for key, item in source_map.items():
        success_count = int(item.get('success_count') or 0)
        failure_count = int(item.get('failure_count') or 0)
        total_attempts = success_count + failure_count
        error_rate = round((failure_count / total_attempts), 3) if total_attempts else 0.0
        last_fetch = item.get('last_fetch')
        last_dt = parse_dt(last_fetch)
        stale = not last_dt or (utc_now() - last_dt) > timedelta(hours=48)
        if total_attempts and error_rate >= 0.5:
            status = 'error'
        elif stale or failure_count > 0:
            status = 'warning'
        else:
            status = 'healthy'
        items.append({
            'source_id': item.get('source_id') or key,
            'source_key': key,
            'platform': item.get('platform') or 'unknown',
            'last_fetch': last_fetch,
            'last_fetch_display': fmt_compact_dt(last_fetch),
            'last_fetch_ago': rel_time(last_fetch),
            'clips_24h': recent_clips.get(key, 0),
            'status': status,
            'error_rate': error_rate,
            'success_count': success_count,
            'failure_count': failure_count,
            'last_error': item.get('last_error'),
        })

    severity = {'error': 0, 'warning': 1, 'healthy': 2}
    items.sort(key=lambda row: (severity.get(row['status'], 9), row['platform'], row['source_id']))
    return items


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


def get_discord_feed() -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    try:
        with urlrequest.urlopen(f'{CONTROL_API_BASE}/api/discord_feed', timeout=15) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        if not payload.get('ok'):
            raise ValueError(payload.get('error') or 'Discord feed endpoint failed')
        messages = payload.get('messages') or []
    except Exception:
        try:
            from control_api import fetch_recent_discord_messages
            messages = fetch_recent_discord_messages(limit=10)
        except Exception:
            return []

    normalized: list[dict[str, Any]] = []
    for msg in messages:
        timestamp = msg.get('timestamp')
        normalized.append({
            'id': msg.get('id'),
            'channel_id': msg.get('channel_id'),
            'channel_name': msg.get('channel_name') or 'discord',
            'author': msg.get('author') or 'Unknown',
            'timestamp': timestamp,
            'timestamp_display': fmt_compact_dt(timestamp),
            'timestamp_ago': rel_time(timestamp),
            'message': (msg.get('message') or '').strip(),
            'message_snippet': ((msg.get('message') or '').strip()[:140]),
            'url': msg.get('url'),
        })

    normalized.sort(key=lambda item: parse_dt(item['timestamp']) or datetime.min, reverse=True)
    return normalized[:DISCORD_FEED_LIMIT]


def get_current_settings(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    channel_rows = query_all(conn, "SELECT channel_name, daily_target FROM channels ORDER BY channel_name")
    settings: dict[str, dict[str, Any]] = {}
    for row in channel_rows:
        channel = row['channel_name']
        sources = CHANNEL_SOURCES.get(channel, [])
        source_values = [source for source in sources if isinstance(source, dict)]
        first_source = source_values[0] if source_values else {}
        settings[channel] = {
            'min_views': int(first_source.get('min_views', 0) or 0),
            'max_per_run': int(first_source.get('max_per_run', SOURCE_DEFAULTS.get('max_per_run', 5)) or SOURCE_DEFAULTS.get('max_per_run', 5)),
            'crop_anchor': first_source.get('crop_anchor', 'center') or 'center',
            'daily_target': int(row['daily_target'] or 0),
            'source_count': len(source_values),
        }
    return settings


def build_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    queue_monitor = get_queue_monitor(conn)
    queue_status = get_queue_status(conn)
    channel_performance = get_channel_performance(conn)
    analytics = load_channel_trends(conn)
    source_health = get_source_health(conn)
    error_analysis = get_error_analysis(conn)
    lagging = [item for item in channel_performance if item['lagging']]
    payload = {
        'generated_at': utc_now().isoformat() + 'Z',
        'repo_root': str(REPO_ROOT),
        'database_path': str(DB_PATH),
        'live_status': get_live_status(conn),
        'queue_monitor': queue_monitor,
        'queue': queue_status,
        'channel_performance': channel_performance,
        'analytics': analytics,
        'source_health': source_health,
        'error_analysis': error_analysis,
        'top_clips': get_top_clips(conn),
        'recent_uploads': get_recent_uploads(conn),
        'recent_clips': get_recent_clips(conn),
        'discord_feed': get_discord_feed(),
        'logs_preview': get_logs_preview(conn),
        'controls': get_controls_metadata(conn),
        'current_settings': get_current_settings(conn),
        'insights': {
            'lagging_channels': lagging[:6],
            'lagging_count': len(lagging),
            'queue_backlog': sum(1 for row in queue_monitor if row['status'] in {'queued', 'running'}),
            'analytics_channels': len(analytics),
        },
        'meta': {
            'refresh_seconds': REFRESH_SECONDS,
            'channel_count': int(query_one(conn, "SELECT COUNT(*) AS c FROM channels")['c']),
            'job_count': int(query_one(conn, "SELECT COUNT(*) AS c FROM publish_jobs")['c']),
            'has_metrics_daily': int(query_one(conn, "SELECT COUNT(*) AS c FROM metrics_daily")['c']) > 0,
            'has_clip_assets': int(query_one(conn, "SELECT COUNT(*) AS c FROM clip_assets")['c']) > 0,
            'note': 'Trend analytics prefer metrics_daily and fall back to source clip proxy series when upload analytics are sparse.',
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
    print(f"Analytics channels: {payload['insights']['analytics_channels']}")
    print(f"Error types tracked: {payload['error_analysis']['distinct_errors']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

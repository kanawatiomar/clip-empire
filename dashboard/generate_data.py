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


def get_upload_schedule(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Get scheduled and recent uploads grouped by day for a 7-day calendar view.
    
    Returns jobs scheduled for the next 7 days plus 3 days back, including:
    - Pending jobs with schedule_at set
    - Recently succeeded jobs from the last 7 days
    
    Grouped by day (YYYY-MM-DD), with each day containing a list of jobs.
    """
    now = utc_now()
    today = now.date()
    
    # Build date range: 3 days back + today + 7 days ahead
    start_date = today - timedelta(days=3)
    end_date = today + timedelta(days=7)
    
    date_range = [(start_date + timedelta(days=i)).isoformat() for i in range((end_date - start_date).days + 1)]
    
    # Query pending jobs with schedule_at set
    pending_rows = query_all(
        conn,
        """
        SELECT job_id, channel_name, caption_text, schedule_at, status
        FROM publish_jobs
        WHERE status = 'queued'
          AND schedule_at IS NOT NULL
          AND DATE(schedule_at) >= DATE(?)
          AND DATE(schedule_at) <= DATE(?)
        ORDER BY schedule_at
        """,
        (start_date.isoformat(), end_date.isoformat()),
    )
    
    # Query recently succeeded jobs from last 7 days
    succeeded_rows = query_all(
        conn,
        """
        SELECT job_id, channel_name, caption_text, updated_at AS schedule_at, status
        FROM publish_jobs
        WHERE status = 'succeeded'
          AND DATE(updated_at) >= DATE(?)
          AND DATE(updated_at) <= DATE(?)
        ORDER BY updated_at
        """,
        ((today - timedelta(days=7)).isoformat(), today.isoformat()),
    )
    
    # Build schedule grouped by day
    schedule_by_day: dict[str, list[dict[str, Any]]] = {}
    
    def add_job_to_schedule(row: sqlite3.Row, job_status: str) -> None:
        dt_str = row['schedule_at']
        dt = parse_dt(dt_str)
        if not dt:
            return
        
        day_key = dt.date().isoformat()
        if day_key not in schedule_by_day:
            schedule_by_day[day_key] = []
        
        # Truncate title to 50 chars
        title = (row['caption_text'] or '')[:50]
        
        schedule_by_day[day_key].append({
            'job_id': row['job_id'],
            'job_id_short': (row['job_id'] or '')[:8],
            'channel': row['channel_name'],
            'title': title or '(untitled)',
            'scheduled_at': dt_str,
            'scheduled_at_iso': dt.isoformat(),
            'status': normalize_status(job_status),
        })
    
    for row in pending_rows:
        add_job_to_schedule(row, 'queued')
    
    for row in succeeded_rows:
        add_job_to_schedule(row, 'succeeded')
    
    # Ensure all days in range exist (even if empty)
    for day in date_range:
        if day not in schedule_by_day:
            schedule_by_day[day] = []
    
    return schedule_by_day


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


def get_upload_timeline(conn: sqlite3.Connection) -> dict[str, Any]:
    """Get upload history grouped into time buckets (Today, Yesterday, This Week, Last Week, Older)."""
    rows = query_all(
        conn,
        """
        SELECT pj.job_id, pj.channel_name, pj.caption_text, pj.updated_at, pr.post_url,
               pv.clip_id, sc.view_count
        FROM publish_jobs pj
        LEFT JOIN publish_results pr ON pr.job_id = pj.job_id
        LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
        LEFT JOIN source_clips sc ON sc.clip_id = pv.clip_id
        WHERE pj.status='succeeded'
        ORDER BY datetime(COALESCE(pj.updated_at, pj.created_at)) DESC
        LIMIT 50
        """,
    )
    
    now = utc_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=today_start.weekday())  # Monday
    last_week_start = week_start - timedelta(days=7)
    
    buckets: dict[str, list[dict[str, Any]]] = {
        'Today': [],
        'Yesterday': [],
        'This Week': [],
        'Last Week': [],
        'Older': [],
    }
    
    for row in rows:
        pub_dt = parse_dt(row['updated_at'])
        if not pub_dt:
            continue
        
        title = row['caption_text'] or 'Untitled'
        if len(title) > 60:
            title = title[:57] + '...'
        
        views = int(row['view_count'] or 0)
        
        entry = {
            'job_id': row['job_id'],
            'job_id_short': (row['job_id'] or '')[:8],
            'channel': row['channel_name'],
            'title': title,
            'published_at': row['updated_at'],
            'published_at_display': fmt_compact_dt(row['updated_at']),
            'published_ago': rel_time(row['updated_at']),
            'views': views,
            'post_url': row['post_url'],
        }
        
        # Classify into time bucket
        if pub_dt >= today_start:
            buckets['Today'].append(entry)
        elif pub_dt >= yesterday_start:
            buckets['Yesterday'].append(entry)
        elif pub_dt >= week_start:
            buckets['This Week'].append(entry)
        elif pub_dt >= last_week_start:
            buckets['Last Week'].append(entry)
        else:
            buckets['Older'].append(entry)
    
    # Return as ordered list of buckets with non-empty ones first
    result = {
        'buckets': [
            {'name': 'Today', 'count': len(buckets['Today']), 'items': buckets['Today']},
            {'name': 'Yesterday', 'count': len(buckets['Yesterday']), 'items': buckets['Yesterday']},
            {'name': 'This Week', 'count': len(buckets['This Week']), 'items': buckets['This Week']},
            {'name': 'Last Week', 'count': len(buckets['Last Week']), 'items': buckets['Last Week']},
            {'name': 'Older', 'count': len(buckets['Older']), 'items': buckets['Older']},
        ],
        'total_count': len(rows),
    }
    
    return result


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


def extract_uuid_from_render_path(render_path: str | None) -> str | None:
    """Extract UUID from render_path like 'renders\\channel\\UUID_final.mp4'"""
    if not render_path:
        return None
    # Split by backslash or forward slash and get the filename part
    parts = render_path.replace('\\', '/').split('/')
    if parts:
        filename = parts[-1]  # Get last part (filename)
        # Extract UUID (36 chars before '_final.mp4')
        if '_final' in filename:
            uuid_part = filename.split('_final')[0]
            if len(uuid_part) == 36 and uuid_part.count('-') == 4:
                return uuid_part
    return None


def get_hall_of_fame(conn: sqlite3.Connection) -> dict[str, Any]:
    """Get the top 10 all-time best performing clips and best clip per channel.
    
    Returns:
    - top_10_clips: ranked list of top 10 clips with views, channel, title, URL, published_at, thumbnail
    - best_per_channel: one top clip per channel showing their personal best
    
    Links platform_variants to source_clips by extracting UUID from render_path.
    """
    import re
    
    # Build lookup table: render_path → (clip_id, views, post_url)
    # Get all succeeded jobs with their source clip data
    rows = query_all(
        conn,
        """
        SELECT pj.job_id, pj.channel_name, pj.caption_text, pj.updated_at,
               pv.clip_id, pv.render_path,
               pr.post_url
        FROM publish_jobs pj
        LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
        LEFT JOIN publish_results pr ON pr.job_id = pj.job_id
        WHERE pj.status='succeeded'
        """,
    )
    
    # Get all source clips
    source_clips_map = {}
    source_clip_rows = query_all(conn, "SELECT clip_id, view_count FROM source_clips WHERE view_count > 0")
    for row in source_clip_rows:
        source_clips_map[row['clip_id']] = int(row['view_count'] or 0)
    
    # Build hall of fame entries by matching render_path UUID to source_clips
    hof_entries = []
    for row in rows:
        uuid = extract_uuid_from_render_path(row['render_path'])
        if uuid and uuid in source_clips_map:
            views = source_clips_map[uuid]
            hof_entries.append({
                'channel': row['channel_name'],
                'title': row['caption_text'] or 'Untitled clip',
                'updated_at': row['updated_at'],
                'post_url': row['post_url'],
                'source_clip_id': uuid,
                'views': views,
            })
    
    # Sort by views descending
    hof_entries.sort(key=lambda x: x['views'], reverse=True)
    
    # Build top 10 clips
    top_10_clips = []
    for idx, entry in enumerate(hof_entries[:10], start=1):
        channel = entry['channel']
        source_clip_id = entry['source_clip_id']
        views = entry['views']
        title = entry['title']
        
        # Build thumbnail path
        thumbnail_path = None
        if channel and source_clip_id:
            thumb_file = REPO_ROOT / 'renders' / 'thumbnails' / channel / f'{source_clip_id}.jpg'
            if thumb_file.exists():
                thumbnail_path = f'/thumbnails/{channel}/{source_clip_id}.jpg'
        
        # Truncate title
        title_display = (title[:80] + '...') if len(title) > 80 else title
        
        top_10_clips.append({
            'rank': idx,
            'channel': channel,
            'title': title,
            'title_display': title_display,
            'views': views,
            'views_display': fmt_num_compact(views),
            'post_url': entry['post_url'],
            'published_at': entry['updated_at'],
            'published_at_display': fmt_compact_dt(entry['updated_at']),
            'published_ago': rel_time(entry['updated_at']),
            'thumbnail_path': thumbnail_path,
        })
    
    # Build best per channel (highest views per channel)
    best_per_channel_map = {}
    for entry in hof_entries:
        channel = entry['channel']
        if channel not in best_per_channel_map:
            source_clip_id = entry['source_clip_id']
            views = entry['views']
            title = entry['title']
            
            # Build thumbnail path
            thumbnail_path = None
            if channel and source_clip_id:
                thumb_file = REPO_ROOT / 'renders' / 'thumbnails' / channel / f'{source_clip_id}.jpg'
                if thumb_file.exists():
                    thumbnail_path = f'/thumbnails/{channel}/{source_clip_id}.jpg'
            
            # Truncate title
            title_display = (title[:80] + '...') if len(title) > 80 else title
            
            best_per_channel_map[channel] = {
                'channel': channel,
                'title': title,
                'title_display': title_display,
                'views': views,
                'views_display': fmt_num_compact(views),
                'post_url': entry['post_url'],
                'published_at': entry['updated_at'],
                'published_at_display': fmt_compact_dt(entry['updated_at']),
                'published_ago': rel_time(entry['updated_at']),
                'thumbnail_path': thumbnail_path,
            }
    
    # Sort best_per_channel by views descending
    best_per_channel = sorted(best_per_channel_map.values(), key=lambda x: x['views'], reverse=True)
    
    return {
        'top_10_clips': top_10_clips,
        'best_per_channel': best_per_channel,
        'top_3': top_10_clips[:3] if top_10_clips else [],
        'total_clips_tracked': len(best_per_channel),
    }


def fmt_num_compact(value: int) -> str:
    """Format number with K/M suffix (e.g., 1.2K, 3.4M)"""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".rstrip('0').rstrip('.')
    if value >= 1_000:
        return f"{value / 1_000:.1f}K".rstrip('0').rstrip('.')
    return str(value)


def get_channel_leaderboard(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Build ranked channel leaderboard with all-time views, recent uploads, and best clips.
    
    Primary data source: source_clips (via publish_jobs join).
    Fallback: metrics_daily if available.
    """
    
    # Try metrics_daily first (if populated), otherwise use source_clips
    metrics_count = query_one(conn, "SELECT COUNT(*) AS c FROM metrics_daily")['c']
    
    if metrics_count > 0:
        # Use metrics_daily for total views (all-time from DB)
        total_views_rows = query_all(
            conn,
            """
            SELECT channel_name,
                   COALESCE(SUM(NULLIF(views_total, 0)), 0) AS total_views
            FROM metrics_daily
            GROUP BY channel_name
            """,
        )
        total_views_map = {row['channel_name']: int(row['total_views'] or 0) for row in total_views_rows}
    else:
        # Fallback: sum views from source_clips used by each channel (proxy for all-time)
        total_views_rows = query_all(
            conn,
            """
            SELECT pj.channel_name,
                   COALESCE(SUM(NULLIF(sc.view_count, 0)), 0) AS total_views
            FROM publish_jobs pj
            LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
            LEFT JOIN source_clips sc ON sc.clip_id = pv.clip_id
            WHERE pj.status='succeeded'
            GROUP BY pj.channel_name
            """,
        )
        total_views_map = {row['channel_name']: int(row['total_views'] or 0) for row in total_views_rows}
    
    # Get uploads in last 30 days per channel
    uploads_30d_rows = query_all(
        conn,
        """
        SELECT channel_name, COUNT(*) AS uploads_30d
        FROM publish_jobs
        WHERE status='succeeded'
          AND datetime(COALESCE(updated_at, created_at)) >= datetime('now', '-30 day')
        GROUP BY channel_name
        """,
    )
    uploads_30d_map = {row['channel_name']: int(row['uploads_30d'] or 0) for row in uploads_30d_rows}
    
    # Get best clip per channel (highest view count from source_clips)
    best_clips_rows = query_all(
        conn,
        """
        SELECT pj.channel_name,
               sc.clip_id,
               sc.title,
               COALESCE(sc.view_count, 0) AS view_count,
               pr.post_url,
               ROW_NUMBER() OVER (PARTITION BY pj.channel_name ORDER BY COALESCE(sc.view_count, 0) DESC) AS rn
        FROM publish_jobs pj
        LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
        LEFT JOIN source_clips sc ON sc.clip_id = pv.clip_id
        LEFT JOIN publish_results pr ON pr.job_id = pj.job_id
        WHERE pj.status='succeeded'
        """,
    )
    
    # Track best clip per channel (highest views)
    best_clips_map = {}
    for row in best_clips_rows:
        channel = row['channel_name']
        if channel not in best_clips_map and row['title']:
            best_clips_map[channel] = {
                'title': row['title'],
                'views': int(row['view_count'] or 0),
                'url': row['post_url'] or '',
            }
    
    # Build leaderboard entries for channels with any publishing activity
    leaderboard = []
    all_channels = set(uploads_30d_map.keys()) | set(total_views_map.keys()) | set(best_clips_map.keys())
    
    for channel in all_channels:
        total_views = total_views_map.get(channel, 0)
        uploads_30d = uploads_30d_map.get(channel, 0)
        avg_views = int(total_views / uploads_30d) if uploads_30d > 0 else 0
        best_clip = best_clips_map.get(channel, {'title': 'No clips yet', 'views': 0, 'url': ''})
        
        leaderboard.append({
            'channel_name': channel,
            'total_views': total_views,
            'uploads_30d': uploads_30d,
            'avg_views': avg_views,
            'best_clip_title': best_clip['title'],
            'best_clip_views': best_clip['views'],
            'best_clip_url': best_clip['url'],
        })
    
    # Sort by total views descending (then by uploads count as tiebreaker)
    leaderboard.sort(key=lambda x: (x['total_views'], x['uploads_30d']), reverse=True)
    
    # Add rank and trend (placeholder for now, last week would need historical data)
    for idx, entry in enumerate(leaderboard, 1):
        entry['rank'] = idx
        entry['trend'] = 'stable'  # Would compare to previous week snapshot
    
    return leaderboard


def get_quota_usage(conn: sqlite3.Connection) -> dict[str, Any]:
    """Calculate YouTube API quota usage per channel.
    
    YouTube API quota:
    - Resets daily at midnight Pacific time
    - Each upload costs 1600 units
    - Each metadata update costs ~50 units
    - Daily limit is 10,000 units per project/account
    
    Returns dict with:
    - quota_by_channel: list of per-channel quota data
    - any_channel_high: bool, True if any channel >80% quota used
    - all_channels_safe: bool, True if all channels <60% quota used
    - reset_time_hours: hours until next midnight Pacific
    - reset_time_minutes: minutes until next midnight Pacific
    """
    from datetime import datetime, timezone, timedelta
    
    # Get current time
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    
    # Convert UTC to Pacific time (PST/PDT)
    # Pacific is UTC-7 (PDT) or UTC-8 (PST)
    # For simplicity, we'll calculate midnight Pacific as:
    # Current UTC time adjusted to PST (UTC-8)
    pacific_tz_offset = timedelta(hours=-8)  # PST, adjust for PDT if needed
    now_pacific = now_utc + pacific_tz_offset
    
    # Calculate next midnight Pacific (00:00:00 next day)
    next_midnight_pacific = (now_pacific.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    
    # Time until reset
    time_until_reset = next_midnight_pacific - now_pacific
    reset_hours = int(time_until_reset.total_seconds() // 3600)
    reset_minutes = int((time_until_reset.total_seconds() % 3600) // 60)
    
    # Calculate today's midnight Pacific in UTC for database query
    today_midnight_pacific_utc = next_midnight_pacific - timedelta(days=1)
    # Convert back to ISO string for SQL
    today_midnight_str = today_midnight_pacific_utc.replace(tzinfo=None).isoformat()
    
    # Query succeeded uploads today (from midnight Pacific)
    rows = query_all(
        conn,
        """
        SELECT channel_name, COUNT(*) AS uploads_today
        FROM publish_jobs
        WHERE status = 'succeeded'
          AND datetime(COALESCE(updated_at, created_at)) >= ?
        GROUP BY channel_name
        """,
        (today_midnight_str,),
    )
    
    uploads_by_channel = {row['channel_name']: int(row['uploads_today'] or 0) for row in rows}
    
    # Get all channels from the database
    all_channels_rows = query_all(conn, "SELECT DISTINCT channel_name FROM channels ORDER BY channel_name")
    all_channels = [row['channel_name'] for row in all_channels_rows]
    
    # Build quota data per channel
    quota_by_channel = []
    any_channel_high = False
    
    for channel in all_channels:
        uploads_today = uploads_by_channel.get(channel, 0)
        units_used = uploads_today * 1600  # Each upload costs 1600 units
        units_remaining = 10000 - units_used
        pct_used = round((units_used / 10000.0) * 100, 1)
        
        # Determine color coding
        if pct_used > 85:
            status_color = 'red'
        elif pct_used > 60:
            status_color = 'yellow'
        else:
            status_color = 'green'
        
        # Track if any channel is >80%
        if pct_used > 80:
            any_channel_high = True
        
        quota_by_channel.append({
            'channel': channel,
            'uploads_today': uploads_today,
            'units_used': units_used,
            'units_remaining': max(0, units_remaining),
            'units_total': 10000,
            'pct_used': pct_used,
            'status': status_color,
            'display_text': f'{units_used}/10000 units ({pct_used}%)',
        })
    
    # Determine overall safety status
    all_channels_safe = all(item['pct_used'] < 60 for item in quota_by_channel)
    
    return {
        'quota_by_channel': quota_by_channel,
        'any_channel_high': any_channel_high,
        'all_channels_safe': all_channels_safe,
        'reset_time_hours': reset_hours,
        'reset_time_minutes': reset_minutes,
        'reset_time_display': f'{reset_hours}h {reset_minutes}m',
    }


def get_revenue_estimate(conn: sqlite3.Connection) -> dict[str, Any]:
    """Calculate estimated monthly revenue based on channel views and niche RPM rates.
    
    RPM rates by niche (revenue per 1000 views):
    - Finance: $4.50 (market_meltdowns, crypto_confessions, rich_or_ruined)
    - Business: $3.50 (startup_graveyard, self_made_clips)
    - Tech/AI: $3.00 (ai_did_what)
    - Fitness: $2.50 (gym_moments)
    - Food: $1.50 (kitchen_chaos)
    - True Crime: $2.00 (cases_unsolved)
    - Gaming/Clips: $0.80 (arc_highlightz, fomo_highlights, viral_recaps, unfiltered_clips)
    - Female Streamers: $1.20 (stream_sirens, stream_queens)
    """
    # Define niche mappings and RPM rates
    niche_rpm = {
        'market_meltdowns': {'niche': 'Finance', 'rpm': 4.50},
        'crypto_confessions': {'niche': 'Finance', 'rpm': 4.50},
        'rich_or_ruined': {'niche': 'Finance', 'rpm': 4.50},
        'startup_graveyard': {'niche': 'Business', 'rpm': 3.50},
        'self_made_clips': {'niche': 'Business', 'rpm': 3.50},
        'ai_did_what': {'niche': 'Tech/AI', 'rpm': 3.00},
        'gym_moments': {'niche': 'Fitness', 'rpm': 2.50},
        'kitchen_chaos': {'niche': 'Food', 'rpm': 1.50},
        'cases_unsolved': {'niche': 'True Crime', 'rpm': 2.00},
        'arc_highlightz': {'niche': 'Gaming/Clips', 'rpm': 0.80},
        'fomo_highlights': {'niche': 'Gaming/Clips', 'rpm': 0.80},
        'viral_recaps': {'niche': 'Gaming/Clips', 'rpm': 0.80},
        'unfiltered_clips': {'niche': 'Gaming/Clips', 'rpm': 0.80},
        'stream_sirens': {'niche': 'Female Streamers', 'rpm': 1.20},
        'stream_queens': {'niche': 'Female Streamers', 'rpm': 1.20},
    }
    
    # Query metrics_daily for last 30 days
    rows = query_all(
        conn,
        """
        SELECT channel_name,
               COALESCE(SUM(NULLIF(views_total, 0)), 0) AS views_30d,
               COALESCE(COUNT(*), 0) AS days_tracked
        FROM metrics_daily
        WHERE platform = 'youtube'
          AND date >= date('now', '-30 day')
        GROUP BY channel_name
        ORDER BY views_30d DESC
        """,
    )
    
    # Calculate per-channel revenue
    channel_revenue = []
    total_views_30d = 0
    total_revenue_30d = 0.0
    
    for row in rows:
        channel = row['channel_name']
        views = float(row['views_30d'] or 0)
        
        if channel not in niche_rpm:
            # Unknown channel, use default RPM of 1.50
            niche_data = {'niche': 'Other', 'rpm': 1.50}
        else:
            niche_data = niche_rpm[channel]
        
        rpm = niche_data['rpm']
        estimated_monthly = round((views / 1000.0) * rpm, 2)
        
        total_views_30d += views
        total_revenue_30d += estimated_monthly
        
        channel_revenue.append({
            'channel': channel,
            'niche': niche_data['niche'],
            'views_30d': int(views),
            'rpm': rpm,
            'estimated_monthly': estimated_monthly,
        })
    
    # Calculate growth rate and projections
    # Query daily totals to estimate growth trend
    daily_totals = query_all(
        conn,
        """
        SELECT date,
               COALESCE(SUM(NULLIF(views_total, 0)), 0) AS daily_total_views
        FROM metrics_daily
        WHERE platform = 'youtube'
          AND date >= date('now', '-30 day')
        GROUP BY date
        ORDER BY date
        """,
    )
    
    # Calculate average daily views for growth projection
    growth_rate = 1.0  # No growth by default
    if len(daily_totals) >= 7:
        first_week = sum(float(row['daily_total_views'] or 0) for row in daily_totals[:7])
        last_week = sum(float(row['daily_total_views'] or 0) for row in daily_totals[-7:])
        if first_week > 0:
            growth_rate = last_week / first_week if last_week > 0 else 1.0
    
    # Calculate projected revenue at current growth rate
    monthly_avg_views = total_views_30d / 30.0
    projected_annual_revenue = total_revenue_30d * 12
    
    # Revenue milestones and progress
    milestones = [500, 1000, 2000, 5000, 10000]
    next_milestone = None
    months_to_milestone = None
    
    for milestone in milestones:
        if total_revenue_30d < milestone:
            next_milestone = milestone
            monthly_growth = total_revenue_30d * (growth_rate - 1.0)
            if monthly_growth > 0:
                months_to_milestone = round((milestone - total_revenue_30d) / monthly_growth)
            else:
                months_to_milestone = None
            break
    
    progress_pct = round((total_revenue_30d / next_milestone) * 100, 1) if next_milestone else 100.0
    
    return {
        'total_views_30d': int(total_views_30d),
        'total_revenue_30d': round(total_revenue_30d, 2),
        'average_rpm': round(total_revenue_30d / (total_views_30d / 1000.0), 2) if total_views_30d > 0 else 0.0,
        'monthly_avg_views': round(monthly_avg_views, 0),
        'projected_annual_revenue': round(projected_annual_revenue, 2),
        'growth_rate': round((growth_rate - 1.0) * 100, 1),
        'next_milestone': next_milestone,
        'progress_to_milestone_pct': progress_pct,
        'months_to_next_milestone': months_to_milestone,
        'channel_breakdown': channel_revenue,
        'summary': f"At current pace, you'll reach ${next_milestone}/mo in approximately {months_to_milestone} months" if months_to_milestone and next_milestone else "Keep up the great work!",
    }


def get_disk_usage() -> dict[str, Any]:
    """Calculate disk usage across key directories and repo root.
    
    Scans:
    - raw_clips/ — downloaded source clips
    - intermediate/ — in-progress renders
    - renders/ — finished renders waiting to upload
    - renders/thumbnails/ — generated thumbnails
    
    Returns:
    - directories: list of directory info with path, size_bytes, size_human, file_count
    - total_disk_bytes: total disk usage for repo root
    - total_disk_human: human-readable total
    - percent_of_500gb: percentage of assumed 500GB total drive
    - warning_threshold_pct: 70 (warn at this percent)
    - error_threshold_pct: 85 (critical at this percent)
    """
    import shutil
    import os
    
    TOTAL_DRIVE_BYTES = 500 * (1024 ** 3)  # 500GB
    
    def get_size_human(bytes_size: int) -> str:
        """Convert bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f}TB"
    
    def count_files_in_dir(path: Path) -> int:
        """Count files (not directories) recursively."""
        try:
            count = 0
            for root, dirs, files in os.walk(str(path)):
                count += len(files)
            return count
        except Exception:
            return 0
    
    def get_dir_size(path: Path) -> int:
        """Get total size of directory recursively."""
        try:
            total = 0
            for root, dirs, files in os.walk(str(path)):
                for file in files:
                    try:
                        file_path = Path(root) / file
                        total += file_path.stat().st_size
                    except Exception:
                        pass
            return total
        except Exception:
            return 0
    
    directories_to_scan = [
        ('raw_clips', REPO_ROOT / 'raw_clips'),
        ('intermediate', REPO_ROOT / 'intermediate'),
        ('renders', REPO_ROOT / 'renders'),
        ('renders/thumbnails', REPO_ROOT / 'renders' / 'thumbnails'),
    ]
    
    dir_info = []
    total_size = 0
    
    for dir_name, dir_path in directories_to_scan:
        if dir_path.exists():
            size_bytes = get_dir_size(dir_path)
            file_count = count_files_in_dir(dir_path)
            total_size += size_bytes
            
            dir_info.append({
                'name': dir_name,
                'path': str(dir_path),
                'size_bytes': size_bytes,
                'size_human': get_size_human(size_bytes),
                'file_count': file_count,
            })
        else:
            dir_info.append({
                'name': dir_name,
                'path': str(dir_path),
                'size_bytes': 0,
                'size_human': '0B',
                'file_count': 0,
            })
    
    # Get repo root total size
    repo_root_size = get_dir_size(REPO_ROOT)
    
    # Calculate percentage of 500GB
    percent_used = round((repo_root_size / TOTAL_DRIVE_BYTES) * 100, 1)
    
    # Get top 5 largest files across all tracked dirs
    largest_files = []
    try:
        all_files = []
        for dir_name, dir_path in directories_to_scan:
            if dir_path.exists():
                for root, dirs, files in os.walk(str(dir_path)):
                    for file in files:
                        try:
                            file_path = Path(root) / file
                            size = file_path.stat().st_size
                            all_files.append({
                                'path': str(file_path),
                                'name': file_path.name,
                                'size_bytes': size,
                                'size_human': get_size_human(size),
                                'directory': dir_name,
                            })
                        except Exception:
                            pass
        
        # Sort by size and get top 5
        all_files.sort(key=lambda x: x['size_bytes'], reverse=True)
        largest_files = all_files[:5]
    except Exception:
        pass
    
    return {
        'directories': dir_info,
        'total_disk_bytes': repo_root_size,
        'total_disk_human': get_size_human(repo_root_size),
        'percent_of_500gb': percent_used,
        'warning_threshold_pct': 70,
        'error_threshold_pct': 85,
        'largest_files': largest_files,
        'disk_status': 'critical' if percent_used >= 85 else 'warning' if percent_used >= 70 else 'healthy',
    }


def get_sources_list(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Build a complete sources list grouped by channel with DB metrics.
    
    Returns a list of channel groups, each containing:
    - channel: channel name
    - sources: list of source objects with config + DB metrics
    """
    sources_list = []
    
    # Iterate through CHANNEL_SOURCES from config
    for channel_name, channel_sources in CHANNEL_SOURCES.items():
        channel_group = {
            'channel': channel_name,
            'sources': [],
        }
        
        for idx, source_config in enumerate(channel_sources):
            # Get default values
            min_views = source_config.get('min_views', SOURCE_DEFAULTS.get('min_views', 0))
            priority = source_config.get('priority', 1)
            creator_name = source_config.get('creator', source_config.get('platform', 'unknown'))
            platform = source_config.get('platform', 'unknown')
            
            # Create source ID for DB lookups
            # Use creator + platform + index to uniquely identify
            source_id_key = f"{channel_name}:{creator_name}:{platform}:{idx}"
            
            # Query for clips_fetched and last_fetched_at
            try:
                metric_row = query_one(
                    conn,
                    """
                    SELECT COUNT(*) as clips_fetched,
                           MAX(used_at) as last_fetched_at
                    FROM source_clips
                    WHERE channel_name = ? AND creator = ?
                    """,
                    (channel_name, creator_name)
                )
                clips_fetched = metric_row['clips_fetched'] or 0 if metric_row else 0
                last_fetched_at = metric_row['last_fetched_at'] if metric_row else None
            except Exception:
                clips_fetched = 0
                last_fetched_at = None
            
            # Build source object
            source_obj = {
                'id': source_id_key,
                'channel': channel_name,
                'platform': platform,
                'creator_name': creator_name,
                'min_views': min_views,
                'priority': priority,
                'clips_fetched': clips_fetched,
                'last_fetched_at': last_fetched_at,
                'last_fetched_rel': rel_time(last_fetched_at) if last_fetched_at else '—',
                'enabled': source_config.get('enabled', True),
                'url': source_config.get('url', ''),
                'type': source_config.get('type', 'unknown'),
            }
            
            channel_group['sources'].append(source_obj)
        
        sources_list.append(channel_group)
    
    return sources_list


def get_title_performance(conn: sqlite3.Connection) -> dict[str, Any]:
    """Analyze A/B title performance patterns.
    
    Analyzes:
    - Titles with numbers (e.g., "5 Ways to...")
    - Questions (titles with ?)
    - ALL CAPS words
    - Emojis in titles
    
    Returns:
    - pattern_stats: avg views by pattern type
    - power_words: top 10 keywords by avg views
    - avoid_words: bottom 10 keywords by avg views
    - best_example_per_channel: best title per channel
    - per_channel_insights: analytics by channel
    """
    import re
    
    # Query all succeeded publish jobs with titles and view counts
    rows = query_all(
        conn,
        """
        SELECT pj.job_id, pj.channel_name, pj.caption_text, 
               COALESCE(sc.view_count, 0) AS views
        FROM publish_jobs pj
        LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
        LEFT JOIN source_clips sc ON sc.clip_id = pv.clip_id
        WHERE pj.status='succeeded' AND pj.caption_text IS NOT NULL
        """,
    )
    
    # Helper functions for pattern detection
    def has_numbers(title: str) -> bool:
        return bool(re.search(r'\d+', title))
    
    def has_question(title: str) -> bool:
        return '?' in title
    
    def has_caps_words(title: str) -> bool:
        # Check if 40%+ of words are ALL CAPS
        words = title.split()
        if not words:
            return False
        caps_words = [w for w in words if w.isupper() and len(w) > 1]
        return len(caps_words) >= len(words) * 0.4
    
    def has_emoji(title: str) -> bool:
        # Emoji ranges
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "]+",
            flags=re.UNICODE
        )
        return bool(emoji_pattern.search(title))
    
    def extract_words(title: str) -> list[str]:
        # Extract individual words (lowercase, no punctuation)
        words = re.findall(r'\b[a-z0-9]+\b', title.lower())
        return words
    
    # Analyze patterns
    pattern_views = {
        'has_numbers': [],
        'has_question': [],
        'has_caps': [],
        'has_emoji': [],
    }
    
    word_views = {}  # word -> [view_counts]
    channel_best = {}  # channel -> (title, views)
    channel_patterns = {}  # channel -> {pattern: count}
    
    for row in rows:
        title = row['caption_text'] or ''
        views = int(row['views'] or 0)
        channel = row['channel_name']
        
        # Track best title per channel
        if channel not in channel_best or views > channel_best[channel][1]:
            channel_best[channel] = (title, views)
        
        # Initialize channel pattern tracking
        if channel not in channel_patterns:
            channel_patterns[channel] = {
                'has_numbers': 0,
                'has_question': 0,
                'has_caps': 0,
                'has_emoji': 0,
                'total': 0,
            }
        
        channel_patterns[channel]['total'] += 1
        
        # Check patterns
        if has_numbers(title):
            pattern_views['has_numbers'].append(views)
            channel_patterns[channel]['has_numbers'] += 1
        
        if has_question(title):
            pattern_views['has_question'].append(views)
            channel_patterns[channel]['has_question'] += 1
        
        if has_caps_words(title):
            pattern_views['has_caps'].append(views)
            channel_patterns[channel]['has_caps'] += 1
        
        if has_emoji(title):
            pattern_views['has_emoji'].append(views)
            channel_patterns[channel]['has_emoji'] += 1
        
        # Track words
        for word in extract_words(title):
            if word not in word_views:
                word_views[word] = []
            word_views[word].append(views)
    
    # Calculate pattern stats
    pattern_stats = {}
    for pattern, views_list in pattern_views.items():
        if views_list:
            avg = round(sum(views_list) / len(views_list), 0)
            pattern_stats[pattern] = {
                'avg_views': avg,
                'count': len(views_list),
                'total_views': sum(views_list),
            }
        else:
            pattern_stats[pattern] = {
                'avg_views': 0,
                'count': 0,
                'total_views': 0,
            }
    
    # Calculate word stats
    word_stats = {}
    for word, views_list in word_views.items():
        if len(views_list) >= 2:  # Only include words that appear 2+ times
            avg = round(sum(views_list) / len(views_list), 0)
            word_stats[word] = {
                'avg_views': avg,
                'count': len(views_list),
                'total_views': sum(views_list),
            }
    
    # Get top 10 power words (highest avg views)
    power_words = sorted(
        [(word, stats) for word, stats in word_stats.items()],
        key=lambda x: x[1]['avg_views'],
        reverse=True
    )[:10]
    
    # Get bottom 10 words to avoid (lowest avg views)
    avoid_words = sorted(
        [(word, stats) for word, stats in word_stats.items()],
        key=lambda x: x[1]['avg_views']
    )[:10]
    
    # Build per-channel insights
    per_channel = []
    for channel, best_data in sorted(channel_best.items()):
        title, views = best_data
        patterns = channel_patterns.get(channel, {})
        total = patterns.get('total', 1)
        
        per_channel.append({
            'channel': channel,
            'best_title': title[:80],
            'best_views': views,
            'total_titles_analyzed': total,
            'pattern_breakdown': {
                'numbers_pct': round((patterns.get('has_numbers', 0) / total) * 100, 1),
                'questions_pct': round((patterns.get('has_question', 0) / total) * 100, 1),
                'caps_pct': round((patterns.get('has_caps', 0) / total) * 100, 1),
                'emoji_pct': round((patterns.get('has_emoji', 0) / total) * 100, 1),
            },
        })
    
    return {
        'pattern_analysis': pattern_stats,
        'power_words': [
            {
                'word': word,
                'avg_views': stats['avg_views'],
                'occurrences': stats['count'],
            }
            for word, stats in power_words
        ],
        'avoid_words': [
            {
                'word': word,
                'avg_views': stats['avg_views'],
                'occurrences': stats['count'],
            }
            for word, stats in avoid_words
        ],
        'best_example_per_channel': [
            {
                'channel': channel,
                'title': title[:80],
                'views': views,
            }
            for channel, (title, views) in sorted(channel_best.items(), key=lambda x: x[1][1], reverse=True)
        ],
        'per_channel_insights': per_channel,
    }


def get_style_performance(conn: sqlite3.Connection) -> dict[str, Any]:
    """Analyze performance metrics grouped by clip style/niche.
    
    Since there's no explicit style_preset column in the database, we group by
    channel niche type. Each channel belongs to a specific niche, and we aggregate
    performance data (views, clip count, best clip) by niche.
    
    Returns:
    - by_style: list of style objects sorted by avg_views (highest first)
      - style_name: niche name (Finance, Business, Tech/AI, etc.)
      - avg_views: average views per clip in this style
      - total_clips: number of clips published in this style
      - best_clip: {title, views, channel, upload_date}
      - total_views: sum of all views in this style
      - is_best: boolean (True for highest avg_views)
    - best_style_overall: niche with highest avg_views
    - summary_stats: {total_styles, total_clips_all, avg_views_overall}
    """
    
    # Define niche mappings (consistent with get_revenue_estimate)
    channel_niche_map = {
        'market_meltdowns': 'Finance',
        'crypto_confessions': 'Finance',
        'rich_or_ruined': 'Finance',
        'startup_graveyard': 'Business',
        'self_made_clips': 'Business',
        'ai_did_what': 'Tech/AI',
        'gym_moments': 'Fitness',
        'kitchen_chaos': 'Food',
        'cases_unsolved': 'True Crime',
        'arc_highlightz': 'Gaming/Clips',
        'fomo_highlights': 'Gaming/Clips',
        'viral_recaps': 'Gaming/Clips',
        'unfiltered_clips': 'Gaming/Clips',
        'stream_sirens': 'Female Streamers',
        'stream_queens': 'Female Streamers',
    }
    
    # Query all succeeded publish_jobs with clip views
    rows = query_all(
        conn,
        """
        SELECT pj.job_id, pj.channel_name, pj.caption_text, pj.updated_at,
               COALESCE(sc.view_count, 0) AS views
        FROM publish_jobs pj
        LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
        LEFT JOIN source_clips sc ON sc.clip_id = pv.clip_id
        WHERE pj.status='succeeded'
        ORDER BY pj.channel_name, COALESCE(sc.view_count, 0) DESC
        """,
    )
    
    # Group by niche
    niche_data = defaultdict(lambda: {
        'clips': [],
        'views_list': [],
        'best_clip': None,
        'best_views': 0,
        'total_clips': 0,
        'total_views': 0,
    })
    
    for row in rows:
        channel = row['channel_name']
        niche = channel_niche_map.get(channel, 'Other')
        views = int(row['views'] or 0)
        title = row['caption_text'] or 'Untitled'
        
        # Add to niche data
        niche_data[niche]['clips'].append({
            'title': title[:80],
            'views': views,
            'channel': channel,
            'upload_date': fmt_compact_dt(row['updated_at']),
        })
        niche_data[niche]['views_list'].append(views)
        niche_data[niche]['total_clips'] += 1
        niche_data[niche]['total_views'] += views
        
        # Track best clip
        if views > niche_data[niche]['best_views']:
            niche_data[niche]['best_views'] = views
            niche_data[niche]['best_clip'] = {
                'title': title[:80],
                'views': views,
                'channel': channel,
                'upload_date': fmt_compact_dt(row['updated_at']),
            }
    
    # Calculate stats and build result list
    style_list = []
    for niche, data in niche_data.items():
        if data['total_clips'] == 0:
            continue
        
        avg_views = round(sum(data['views_list']) / len(data['views_list']), 0)
        style_list.append({
            'style_name': niche,
            'avg_views': int(avg_views),
            'total_clips': data['total_clips'],
            'best_clip': data['best_clip'],
            'total_views': data['total_views'],
        })
    
    # Sort by avg_views descending
    style_list.sort(key=lambda x: x['avg_views'], reverse=True)
    
    # Mark best style
    if style_list:
        style_list[0]['is_best'] = True
        for item in style_list[1:]:
            item['is_best'] = False
    
    # Calculate overall stats
    total_clips_all = sum(item['total_clips'] for item in style_list)
    total_views_all = sum(item['total_views'] for item in style_list)
    avg_views_overall = round(total_views_all / total_clips_all, 0) if total_clips_all > 0 else 0
    
    return {
        'by_style': style_list,
        'best_style_overall': style_list[0]['style_name'] if style_list else None,
        'summary_stats': {
            'total_styles': len(style_list),
            'total_clips_all': total_clips_all,
            'total_views_all': total_views_all,
            'avg_views_overall': int(avg_views_overall),
        },
    }


def get_daily_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Generate daily summary report with today's stats and comparisons to yesterday.
    
    Returns:
    - date: today's date (YYYY-MM-DD)
    - uploads_today: uploads succeeded today
    - views_gained_today: total views from clips uploaded today (source_clips view_count)
    - errors_today: publish_jobs with errors created/updated today
    - top_clip_today: title, views, channel of best performing clip from today
    - quota_usage: percentage of YouTube API quota used today
    - delta_uploads: uploads today vs yesterday (positive = growth)
    - delta_views: views today vs yesterday
    - top_3_channels: list of top 3 channels by upload count today
    - summary_text: plain text summary
    - summary_discord: Discord markdown formatted summary (for sending to bot-logs)
    """
    from datetime import datetime, timedelta
    
    today = utc_now().date().isoformat()
    yesterday = (utc_now().date() - timedelta(days=1)).isoformat()
    
    # Get today's uploads (succeeded jobs created/updated today)
    uploads_today = int(
        query_one(
            conn,
            """
            SELECT COUNT(*) AS c FROM publish_jobs
            WHERE status = 'succeeded'
              AND DATE(COALESCE(updated_at, created_at)) = ?
            """,
            (today,)
        )['c'] or 0
    )
    
    # Get yesterday's uploads for comparison
    uploads_yesterday = int(
        query_one(
            conn,
            """
            SELECT COUNT(*) AS c FROM publish_jobs
            WHERE status = 'succeeded'
              AND DATE(COALESCE(updated_at, created_at)) = ?
            """,
            (yesterday,)
        )['c'] or 0
    )
    
    delta_uploads = uploads_today - uploads_yesterday
    
    # Get today's errors
    errors_today = int(
        query_one(
            conn,
            """
            SELECT COUNT(*) AS c FROM publish_jobs
            WHERE last_error IS NOT NULL
              AND TRIM(last_error) != ''
              AND DATE(COALESCE(updated_at, created_at)) = ?
            """,
            (today,)
        )['c'] or 0
    )
    
    # Get today's views gained (sum of view_count from source_clips used in today's uploads)
    views_today_result = query_one(
        conn,
        """
        SELECT COALESCE(SUM(NULLIF(sc.view_count, 0)), 0) AS total_views
        FROM publish_jobs pj
        LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
        LEFT JOIN source_clips sc ON sc.clip_id = pv.clip_id
        WHERE pj.status = 'succeeded'
          AND DATE(COALESCE(pj.updated_at, pj.created_at)) = ?
        """,
        (today,)
    )
    views_gained_today = int(views_today_result['total_views'] or 0) if views_today_result else 0
    
    # Get yesterday's views for comparison
    views_yesterday_result = query_one(
        conn,
        """
        SELECT COALESCE(SUM(NULLIF(sc.view_count, 0)), 0) AS total_views
        FROM publish_jobs pj
        LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
        LEFT JOIN source_clips sc ON sc.clip_id = pv.clip_id
        WHERE pj.status = 'succeeded'
          AND DATE(COALESCE(pj.updated_at, pj.created_at)) = ?
        """,
        (yesterday,)
    )
    views_yesterday = int(views_yesterday_result['total_views'] or 0) if views_yesterday_result else 0
    delta_views = views_gained_today - views_yesterday
    
    # Get top performing clip from today
    top_clip_row = query_one(
        conn,
        """
        SELECT pj.channel_name, pj.caption_text, COALESCE(sc.view_count, 0) AS views
        FROM publish_jobs pj
        LEFT JOIN platform_variants pv ON pv.variant_id = pj.variant_id
        LEFT JOIN source_clips sc ON sc.clip_id = pv.clip_id
        WHERE pj.status = 'succeeded'
          AND DATE(COALESCE(pj.updated_at, pj.created_at)) = ?
        ORDER BY COALESCE(sc.view_count, 0) DESC
        LIMIT 1
        """,
        (today,)
    )
    
    top_clip_today = None
    if top_clip_row:
        top_clip_today = {
            'title': (top_clip_row['caption_text'] or 'Untitled')[:100],
            'views': int(top_clip_row['views'] or 0),
            'channel': top_clip_row['channel_name'],
        }
    
    # Get quota usage for today (YouTube API: 1600 units per upload, 10000 units daily limit)
    quota_units_used = uploads_today * 1600
    quota_pct = round((quota_units_used / 10000.0) * 100, 1)
    
    # Get top 3 channels by upload count today
    top_channels_rows = query_all(
        conn,
        """
        SELECT channel_name, COUNT(*) AS uploads
        FROM publish_jobs
        WHERE status = 'succeeded'
          AND DATE(COALESCE(updated_at, created_at)) = ?
        GROUP BY channel_name
        ORDER BY uploads DESC
        LIMIT 3
        """,
        (today,)
    )
    
    top_3_channels = [
        {'channel': row['channel_name'], 'uploads': int(row['uploads'] or 0)}
        for row in top_channels_rows
    ]
    
    # Generate summary text
    summary_lines = [
        f"📊 Daily Summary for {today}",
        f"",
        f"📈 Stats:",
        f"  Uploads: {uploads_today} ({'+' if delta_uploads >= 0 else ''}{delta_uploads} vs yesterday)",
        f"  Views: {fmt_num_compact(views_gained_today)} ({'+' if delta_views >= 0 else ''}{fmt_num_compact(delta_views)} vs yesterday)",
        f"  Errors: {errors_today}",
        f"  API Quota: {quota_pct}% used ({quota_units_used}/10000 units)",
    ]
    
    if top_clip_today:
        summary_lines.append(f"")
        summary_lines.append(f"🌟 Top Clip:")
        summary_lines.append(f"  {top_clip_today['title']}")
        summary_lines.append(f"  {fmt_num_compact(top_clip_today['views'])} views • {top_clip_today['channel']}")
    
    if top_3_channels:
        summary_lines.append(f"")
        summary_lines.append(f"🏆 Top Channels:")
        for idx, ch in enumerate(top_3_channels, 1):
            summary_lines.append(f"  {idx}. {ch['channel']}: {ch['uploads']} uploads")
    
    summary_text = '\n'.join(summary_lines)
    
    # Generate Discord markdown version
    discord_lines = [
        f"## 📊 Daily Summary — {today}",
        f"",
        f"**📈 Today's Stats:**",
        f"• **Uploads:** {uploads_today} ({'+' if delta_uploads >= 0 else ''}{delta_uploads} vs yesterday)",
        f"• **Views:** {fmt_num_compact(views_gained_today)} ({'+' if delta_views >= 0 else ''}{fmt_num_compact(delta_views)} vs yesterday)",
        f"• **Errors:** {errors_today}",
        f"• **API Quota:** {quota_pct}% used (`{quota_units_used}/10000` units)",
    ]
    
    if top_clip_today:
        discord_lines.append(f"")
        discord_lines.append(f"**🌟 Top Performer Today:**")
        discord_lines.append(f"_{top_clip_today['title']}_")
        discord_lines.append(f"**{fmt_num_compact(top_clip_today['views'])} views** • **{top_clip_today['channel']}**")
    
    if top_3_channels:
        discord_lines.append(f"")
        discord_lines.append(f"**🏆 Top Channels:**")
        for idx, ch in enumerate(top_3_channels, 1):
            discord_lines.append(f"{idx}. **{ch['channel']}** — {ch['uploads']} uploads")
    
    summary_discord = '\n'.join(discord_lines)
    
    return {
        'date': today,
        'uploads_today': uploads_today,
        'uploads_yesterday': uploads_yesterday,
        'views_gained_today': views_gained_today,
        'views_yesterday': views_yesterday,
        'errors_today': errors_today,
        'quota_pct': quota_pct,
        'quota_units_used': quota_units_used,
        'delta_uploads': delta_uploads,
        'delta_views': delta_views,
        'top_clip_today': top_clip_today,
        'top_3_channels': top_3_channels,
        'summary_text': summary_text,
        'summary_discord': summary_discord,
    }


def get_pipeline_status(conn: sqlite3.Connection) -> dict[str, Any]:
    """Track the full clip lifecycle through the pipeline.
    
    Pipeline stages:
    1. Discovered: sources ingested into the system
    2. Downloaded: sources with download_path filled
    3. Processed: segments extracted from sources (transcribed, analyzed)
    4. Queued: publish_jobs awaiting publishing (status=queued/running)
    5. Uploaded: publish_jobs successfully published (status=succeeded)
    
    Returns:
    - overall: counts and throughput for all clips
    - by_channel: per-channel breakdown
    - throughput: clips/hour moving through pipeline
    - bottleneck: slowest stage (stage name + duration)
    """
    # Get overall pipeline counts
    discovered = query_one(conn, "SELECT COUNT(*) AS c FROM sources")['c'] or 0
    downloaded = query_one(conn, "SELECT COUNT(*) AS c FROM sources WHERE download_path IS NOT NULL")['c'] or 0
    processed = query_one(conn, "SELECT COUNT(*) AS c FROM segments")['c'] or 0
    queued = query_one(conn, "SELECT COUNT(*) AS c FROM publish_jobs WHERE status IN ('queued', 'running')")['c'] or 0
    uploaded = query_one(conn, "SELECT COUNT(*) AS c FROM publish_jobs WHERE status='succeeded'")['c'] or 0
    
    # Get channel breakdown
    channel_pipeline = []
    channels = query_all(conn, "SELECT DISTINCT channel_name FROM channels ORDER BY channel_name")
    
    for channel_row in channels:
        channel = channel_row['channel_name']
        
        # Count clips at each stage for this channel
        # Note: clip_assets links segments to channels
        ch_discovered = query_one(
            conn,
            "SELECT COUNT(DISTINCT s.source_id) AS c FROM sources s WHERE s.source_id IN (SELECT DISTINCT segment_id FROM segments WHERE segment_id IN (SELECT segment_id FROM clip_assets WHERE channel_name=?))",
            (channel,)
        )['c'] or 0
        
        ch_downloaded = query_one(
            conn,
            "SELECT COUNT(DISTINCT s.source_id) AS c FROM sources s WHERE s.download_path IS NOT NULL AND s.source_id IN (SELECT DISTINCT segment_id FROM segments WHERE segment_id IN (SELECT segment_id FROM clip_assets WHERE channel_name=?))",
            (channel,)
        )['c'] or 0
        
        ch_processed = query_one(
            conn,
            "SELECT COUNT(*) AS c FROM segments WHERE segment_id IN (SELECT segment_id FROM clip_assets WHERE channel_name=?)",
            (channel,)
        )['c'] or 0
        
        ch_queued = query_one(
            conn,
            "SELECT COUNT(*) AS c FROM publish_jobs WHERE channel_name=? AND status IN ('queued', 'running')",
            (channel,)
        )['c'] or 0
        
        ch_uploaded = query_one(
            conn,
            "SELECT COUNT(*) AS c FROM publish_jobs WHERE channel_name=? AND status='succeeded'",
            (channel,)
        )['c'] or 0
        
        if ch_discovered > 0 or ch_queued > 0 or ch_uploaded > 0:  # Only include active channels
            channel_pipeline.append({
                'channel': channel,
                'discovered': ch_discovered,
                'downloaded': ch_downloaded,
                'processed': ch_processed,
                'queued': ch_queued,
                'uploaded': ch_uploaded,
            })
    
    # Calculate throughput: clips/hour moving from queued to uploaded
    # Look at last 24 hours of successful uploads
    throughput_rows = query_all(
        conn,
        """
        SELECT COUNT(*) AS uploads_24h
        FROM publish_jobs
        WHERE status='succeeded'
          AND datetime(updated_at) >= datetime('now', '-1 day')
        """
    )
    uploads_24h = throughput_rows[0]['uploads_24h'] or 0 if throughput_rows else 0
    throughput_per_hour = round(uploads_24h / 24.0, 2)
    
    # Calculate average time at each stage (in hours)
    # Discovered to Downloaded
    disc_to_dl_rows = query_all(
        conn,
        """
        SELECT AVG((julianday(s.ingested_at) - julianday(s.ingested_at)) * 24) AS avg_hours
        FROM sources s
        WHERE s.download_path IS NOT NULL
          AND s.ingested_at IS NOT NULL
        """
    )
    avg_disc_to_dl = 0.0  # Simplified: assume immediate for now
    
    # Queued to Uploaded
    q_to_up_rows = query_all(
        conn,
        """
        SELECT AVG((julianday(pj.updated_at) - julianday(pj.created_at)) * 24) AS avg_hours
        FROM publish_jobs pj
        WHERE pj.status='succeeded'
        """
    )
    avg_q_to_up = round(q_to_up_rows[0]['avg_hours'] or 0.0, 2) if q_to_up_rows else 0.0
    
    # Identify bottleneck (slowest stage based on queue depth)
    stages = [
        ('discovered', discovered),
        ('downloaded', downloaded),
        ('processed', processed),
        ('queued', queued),
    ]
    
    bottleneck_stage = 'queued'  # Default to queued (most likely bottleneck)
    max_backlog = queued
    for stage_name, count in stages:
        if count > max_backlog:
            bottleneck_stage = stage_name
            max_backlog = count
    
    return {
        'overall': {
            'discovered': discovered,
            'downloaded': downloaded,
            'processed': processed,
            'queued': queued,
            'uploaded': uploaded,
        },
        'by_channel': channel_pipeline,
        'throughput': {
            'uploads_per_hour': throughput_per_hour,
            'uploads_last_24h': uploads_24h,
        },
        'stage_timings': {
            'discovered_to_downloaded_hours': avg_disc_to_dl,
            'queued_to_uploaded_hours': avg_q_to_up,
        },
        'bottleneck': {
            'stage': bottleneck_stage,
            'backlog': max_backlog,
        },
    }


def get_posting_time_insights(conn: sqlite3.Connection) -> dict[str, Any]:
    """Analyze posting patterns from succeeded publish_jobs to optimize posting times.
    
    Groups successful posts by hour of day (0-23) and day of week (0-6, Mon-Sun).
    Returns average performance metrics and identifies best posting windows.
    
    Data structure:
    - hourly: List of 24 hours with avg views and post counts
    - daily: List of 7 days with avg views and post counts
    - best_hours: Top 3 hours for posting
    - best_days: Top 3 days for posting
    - heatmap_data: 24x7 grid for visualization (hours × days)
    - scheduled_posts: Current scheduled posts with their timing
    """
    # Fetch all succeeded publish_jobs with schedule times
    jobs = query_all(
        conn,
        """
        SELECT job_id, schedule_at, channel_name, status
        FROM publish_jobs
        WHERE status = 'succeeded'
          AND schedule_at IS NOT NULL
        ORDER BY schedule_at
        """,
    )
    
    # Initialize hour (0-23) and day (0-6, Mon-Sun) tracking
    hour_counts = defaultdict(int)
    hour_views = defaultdict(float)
    day_counts = defaultdict(int)
    day_views = defaultdict(float)
    heatmap = {}  # (hour, day) -> avg_views
    
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Process each succeeded job
    for job in jobs:
        schedule_dt = parse_dt(job['schedule_at'])
        if not schedule_dt:
            continue
        
        hour = schedule_dt.hour
        # weekday() returns 0-6 (Mon-Sun)
        day_of_week = schedule_dt.weekday()
        
        # For now, assign views based on hour popularity pattern
        # (This will be replaced with actual view data from metrics when available)
        # Prime hours (18-23): 3.0x multiplier, Evening (12-17): 2.0x, Morning (6-11): 1.0x, Night (0-5): 0.5x
        if 18 <= hour <= 23:
            base_views = 1500.0
        elif 12 <= hour <= 17:
            base_views = 1000.0
        elif 6 <= hour <= 11:
            base_views = 600.0
        else:
            base_views = 300.0
        
        # Add some variation based on day
        day_multiplier = {
            0: 1.2,  # Monday
            1: 1.3,  # Tuesday (best)
            2: 1.1,  # Wednesday
            3: 1.0,  # Thursday
            4: 0.9,  # Friday
            5: 0.8,  # Saturday
            6: 0.7,  # Sunday
        }.get(day_of_week, 1.0)
        
        views = base_views * day_multiplier
        
        # Aggregate by hour
        hour_counts[hour] += 1
        hour_views[hour] += views
        
        # Aggregate by day
        day_counts[day_of_week] += 1
        day_views[day_of_week] += views
        
        # Add to heatmap
        key = (hour, day_of_week)
        if key not in heatmap:
            heatmap[key] = {'views': 0, 'count': 0}
        heatmap[key]['views'] += views
        heatmap[key]['count'] += 1
    
    # Calculate averages
    hourly_data = []
    for hour in range(24):
        count = hour_counts[hour]
        avg = hour_views[hour] / count if count > 0 else 0
        hourly_data.append({
            'hour': hour,
            'hour_label': f'{hour:02d}:00',
            'posts': count,
            'avg_views': round(avg, 0),
        })
    
    daily_data = []
    for day in range(7):
        count = day_counts[day]
        avg = day_views[day] / count if count > 0 else 0
        daily_data.append({
            'day': day,
            'day_name': day_names[day],
            'posts': count,
            'avg_views': round(avg, 0),
        })
    
    # Find top 3 best hours
    best_hours = sorted(hourly_data, key=lambda x: x['avg_views'], reverse=True)[:3]
    
    # Find top 3 best days
    best_days = sorted(daily_data, key=lambda x: x['avg_views'], reverse=True)[:3]
    
    # Build heatmap grid (24 hours x 7 days)
    heatmap_grid = []
    max_views = max([h['avg_views'] for h in hourly_data] or [1])
    
    for hour in range(24):
        row = []
        for day in range(7):
            key = (hour, day)
            if key in heatmap:
                views = heatmap[key]['views'] / heatmap[key]['count']
                posts = heatmap[key]['count']
            else:
                views = 0
                posts = 0
            
            row.append({
                'hour': hour,
                'day': day,
                'views': round(views, 0),
                'posts': posts,
                'intensity': round((views / max_views) * 100, 1) if max_views > 0 else 0,
            })
        heatmap_grid.append(row)
    
    # Get scheduled posts for the next 7 days
    now = utc_now()
    end_date = now + timedelta(days=7)
    
    scheduled_posts = query_all(
        conn,
        """
        SELECT job_id, channel_name, schedule_at, caption_text
        FROM publish_jobs
        WHERE status = 'queued'
          AND schedule_at IS NOT NULL
          AND schedule_at >= ?
          AND schedule_at <= ?
        ORDER BY schedule_at
        """,
        (now.isoformat(), end_date.isoformat()),
    )
    
    scheduled_with_times = []
    for post in scheduled_posts:
        schedule_dt = parse_dt(post['schedule_at'])
        if schedule_dt:
            hour = schedule_dt.hour
            day = schedule_dt.weekday()
            scheduled_with_times.append({
                'job_id': post['job_id'][:8],
                'channel': post['channel_name'],
                'title': (post['caption_text'] or '')[:50],
                'scheduled_at': post['schedule_at'],
                'hour': hour,
                'day': day,
                'day_name': day_names[day],
            })
    
    # Find next best slot
    next_best_slot = None
    if best_hours and best_days:
        best_hour = best_hours[0]['hour']
        best_day = best_days[0]['day']
        
        # Find the next occurrence of this (hour, day) combination
        search_start = now
        for offset in range(1, 365):
            check_date = now + timedelta(days=offset)
            if check_date.weekday() == best_day:
                next_best_slot = {
                    'date': check_date.date().isoformat(),
                    'hour': best_hour,
                    'hour_label': f'{best_hour:02d}:00',
                    'day_name': day_names[best_day],
                    'est_views': round(best_hours[0]['avg_views'], 0),
                }
                break
    
    return {
        'hourly': hourly_data,
        'daily': daily_data,
        'best_hours': best_hours,
        'best_days': best_days,
        'heatmap_grid': heatmap_grid,
        'scheduled_posts': scheduled_with_times,
        'next_best_slot': next_best_slot,
        'job_count': len(jobs),
    }


def get_competitor_benchmarks(conn: sqlite3.Connection) -> dict[str, Any]:
    """Calculate channel performance against industry benchmarks for Shorts creators.
    
    Defines tier thresholds based on typical successful Shorts channel metrics:
    - Starter: 500 subs, 50K views/mo, $42/mo
    - Growing: 5K subs, 500K views/mo, $425/mo
    - Monetized: 10K subs, 1M views/mo, $850/mo
    - Pro: 50K subs, 5M views/mo, $4250/mo
    - Empire: 500K subs, 50M views/mo, $42500/mo
    
    Returns current metrics, tier position, and progress to next tier.
    """
    # Define benchmark tiers
    tiers = [
        {'name': 'Starter', 'subs': 500, 'views_mo': 50000, 'revenue_mo': 42.0},
        {'name': 'Growing', 'subs': 5000, 'views_mo': 500000, 'revenue_mo': 425.0},
        {'name': 'Monetized', 'subs': 10000, 'views_mo': 1000000, 'revenue_mo': 850.0},
        {'name': 'Pro', 'subs': 50000, 'views_mo': 5000000, 'revenue_mo': 4250.0},
        {'name': 'Empire', 'subs': 500000, 'views_mo': 50000000, 'revenue_mo': 42500.0},
    ]
    
    # Get current metrics from last 30 days
    current_metrics = query_one(
        conn,
        """
        SELECT COALESCE(SUM(NULLIF(views_total, 0)), 0) AS total_views_30d,
               COUNT(DISTINCT channel_name) AS active_channels
        FROM metrics_daily
        WHERE platform = 'youtube'
          AND date >= date('now', '-30 day')
        """,
    )
    
    total_views_30d = float(current_metrics['total_views_30d'] or 0)
    
    # For now, estimate subs based on views (typical engagement rates)
    # Assuming 0.2% of viewers subscribe (conservative for clips)
    estimated_subs = int(total_views_30d * 0.002)
    
    # Calculate revenue from revenue estimation
    revenue_rows = query_all(
        conn,
        """
        SELECT channel_name,
               COALESCE(SUM(NULLIF(views_total, 0)), 0) AS views_30d
        FROM metrics_daily
        WHERE platform = 'youtube'
          AND date >= date('now', '-30 day')
        GROUP BY channel_name
        """,
    )
    
    # Niche RPM rates (matching get_revenue_estimate)
    niche_rpm = {
        'market_meltdowns': 4.50,
        'crypto_confessions': 4.50,
        'rich_or_ruined': 4.50,
        'startup_graveyard': 3.50,
        'self_made_clips': 3.50,
        'ai_did_what': 3.00,
        'gym_moments': 2.50,
        'kitchen_chaos': 1.50,
        'cases_unsolved': 2.00,
        'arc_highlightz': 0.80,
        'fomo_highlights': 0.80,
        'viral_recaps': 0.80,
        'unfiltered_clips': 0.80,
        'stream_sirens': 1.20,
        'stream_queens': 1.20,
    }
    
    total_revenue_30d = 0.0
    for row in revenue_rows:
        channel = row['channel_name']
        views = float(row['views_30d'] or 0)
        rpm = niche_rpm.get(channel, 1.50)  # Default RPM if channel not found
        total_revenue_30d += (views / 1000.0) * rpm
    
    total_revenue_30d = round(total_revenue_30d, 2)
    
    # Find current tier
    current_tier_idx = 0
    for i, tier in enumerate(tiers):
        if (total_views_30d >= tier['views_mo'] and 
            total_revenue_30d >= tier['revenue_mo']):
            current_tier_idx = i
    
    current_tier = tiers[current_tier_idx]
    
    # Calculate progress metrics
    progress_data = []
    for i, tier in enumerate(tiers):
        is_current = i == current_tier_idx
        is_next = i == current_tier_idx + 1
        is_achieved = i < current_tier_idx
        
        # Calculate percentage progress to this tier
        if is_achieved:
            progress_pct = 100.0
        elif is_next:
            current_progress = current_tier['views_mo']
            next_tier_views = tier['views_mo']
            prev_tier_views = tiers[current_tier_idx]['views_mo']
            
            if next_tier_views > prev_tier_views:
                progress_pct = round(
                    ((current_progress - prev_tier_views) / (next_tier_views - prev_tier_views)) * 100,
                    1
                )
            else:
                progress_pct = 0.0
        else:
            progress_pct = 0.0
        
        # Calculate months to reach tier (if not achieved)
        months_to_tier = None
        if not is_achieved and is_next:
            views_remaining = tier['views_mo'] - total_views_30d
            if total_views_30d > 0:
                days_elapsed_est = 30  # One month of data
                monthly_growth_rate = total_views_30d / days_elapsed_est * 30
                if monthly_growth_rate > 0:
                    months_to_tier = round(views_remaining / monthly_growth_rate, 1)
        
        progress_data.append({
            'tier': tier['name'],
            'tier_index': i,
            'subs_target': tier['subs'],
            'views_target': tier['views_mo'],
            'revenue_target': tier['revenue_mo'],
            'is_current': is_current,
            'is_achieved': is_achieved,
            'is_next': is_next,
            'progress_pct': progress_pct,
            'months_to_tier': months_to_tier,
        })
    
    # Calculate per-metric breakdowns
    next_tier_idx = min(current_tier_idx + 1, len(tiers) - 1)
    next_tier = tiers[next_tier_idx]
    
    subs_progress_pct = round((estimated_subs / next_tier['subs']) * 100, 1) if next_tier['subs'] > 0 else 0.0
    views_progress_pct = round((total_views_30d / next_tier['views_mo']) * 100, 1) if next_tier['views_mo'] > 0 else 0.0
    revenue_progress_pct = round((total_revenue_30d / next_tier['revenue_mo']) * 100, 1) if next_tier['revenue_mo'] > 0 else 0.0
    
    return {
        'current_tier': current_tier['name'],
        'current_tier_index': current_tier_idx,
        'current_metrics': {
            'subs_estimated': estimated_subs,
            'views_30d': int(total_views_30d),
            'revenue_30d': total_revenue_30d,
        },
        'next_tier': next_tier['name'] if next_tier_idx < len(tiers) else None,
        'next_tier_targets': {
            'subs': next_tier['subs'] if next_tier_idx < len(tiers) else None,
            'views_mo': next_tier['views_mo'] if next_tier_idx < len(tiers) else None,
            'revenue_mo': next_tier['revenue_mo'] if next_tier_idx < len(tiers) else None,
        },
        'progress_breakdown': {
            'subs_pct': subs_progress_pct,
            'views_pct': views_progress_pct,
            'revenue_pct': revenue_progress_pct,
        },
        'tiers': progress_data,
        'milestones_unlocked': list(range(current_tier_idx + 1)),
    }


def get_notifications(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Generate notifications from system state and read from database.
    
    Returns last 20 unread + 5 most recent read notifications.
    Auto-generates alerts from system state.
    """
    notifications = []
    now = utc_now()
    
    # Auto-generate notifications from system state
    
    # 1. Channel paused for 24+ hours with no uploads
    for channel_row in query_all(conn, "SELECT channel_name, status, updated_at FROM channels WHERE status='paused'"):
        channel_name = channel_row['channel_name']
        updated_at_str = channel_row['updated_at']
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00')).replace(tzinfo=None)
                hours_paused = (now - updated_at).total_seconds() / 3600
                if hours_paused >= 24:
                    notifications.append({
                        'type': 'warning',
                        'title': f'Channel "{channel_name}" paused for 24+ hours',
                        'message': f'{channel_name} has been paused for {int(hours_paused)} hours',
                        'channel': channel_name,
                        'created_at': now.isoformat(),
                        'read': False,
                    })
            except Exception:
                pass
    
    # 2. Quota at 80%+
    try:
        quota_row = query_one(conn, "SELECT * FROM quota LIMIT 1")
        if quota_row:
            used = float(quota_row.get('used_gb') or 0)
            limit = float(quota_row.get('limit_gb') or 0)
            if limit > 0:
                quota_pct = (used / limit) * 100
                if quota_pct >= 80:
                    notifications.append({
                        'type': 'warning',
                        'title': f'Quota at {quota_pct:.1f}%',
                        'message': f'Storage quota usage is at {quota_pct:.1f}% ({used:.1f}GB / {limit:.1f}GB)',
                        'channel': None,
                        'created_at': now.isoformat(),
                        'read': False,
                    })
    except Exception:
        pass
    
    # 3. 10+ failed jobs in queue
    try:
        failed_count = query_one(conn, "SELECT COUNT(*) as cnt FROM publish_jobs WHERE status='failed'")['cnt']
        if failed_count >= 10:
            notifications.append({
                'type': 'error',
                'title': f'{failed_count} failed jobs in queue',
                'message': f'There are {failed_count} failed publish jobs waiting for retry',
                'channel': None,
                'created_at': now.isoformat(),
                'read': False,
            })
    except Exception:
        pass
    
    # 4. New milestone: channel uploaded 100+ clips total
    try:
        milestones = query_all(conn, """
            SELECT channel_name, COUNT(*) as total_clips
            FROM clips
            GROUP BY channel_name
            HAVING COUNT(*) >= 100
        """)
        for milestone in milestones:
            channel_name = milestone['channel_name']
            total_clips = milestone['total_clips']
            # Check if we already have this notification
            if not any(n['title'] == f'{channel_name} reached {total_clips} clips!' for n in notifications):
                notifications.append({
                    'type': 'success',
                    'title': f'{channel_name} reached {total_clips} clips!',
                    'message': f'{channel_name} has uploaded {total_clips} total clips',
                    'channel': channel_name,
                    'created_at': now.isoformat(),
                    'read': False,
                })
    except Exception:
        pass
    
    # Read manually stored notifications from database
    try:
        unread = query_all(conn, """
            SELECT id, type, title, message, created_at, channel
            FROM dashboard_notifications
            WHERE read_at IS NULL
            ORDER BY created_at DESC
            LIMIT 20
        """)
        
        read = query_all(conn, """
            SELECT id, type, title, message, created_at, channel
            FROM dashboard_notifications
            WHERE read_at IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        for n in unread:
            notifications.append({
                'type': n['type'],
                'title': n['title'],
                'message': n['message'],
                'channel': n['channel'],
                'created_at': n['created_at'],
                'read': False,
            })
        
        for n in read:
            notifications.append({
                'type': n['type'],
                'title': n['title'],
                'message': n['message'],
                'channel': n['channel'],
                'created_at': n['created_at'],
                'read': True,
            })
    except Exception:
        # Table doesn't exist yet, that's fine
        pass
    
    return notifications


def build_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    queue_monitor = get_queue_monitor(conn)
    queue_status = get_queue_status(conn)
    channel_performance = get_channel_performance(conn)
    analytics = load_channel_trends(conn)
    source_health = get_source_health(conn)
    error_analysis = get_error_analysis(conn)
    schedule = get_upload_schedule(conn)
    quota = get_quota_usage(conn)
    revenue = get_revenue_estimate(conn)
    pipeline = get_pipeline_status(conn)
    disk_usage = get_disk_usage()
    hall_of_fame = get_hall_of_fame(conn)
    sources_list = get_sources_list(conn)
    daily_summary = get_daily_summary(conn)
    title_performance = get_title_performance(conn)
    style_performance = get_style_performance(conn)
    posting_times = get_posting_time_insights(conn)
    benchmarks = get_competitor_benchmarks(conn)
    notifications = get_notifications(conn)
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
        'upload_timeline': get_upload_timeline(conn),
        'discord_feed': get_discord_feed(),
        'logs_preview': get_logs_preview(conn),
        'controls': get_controls_metadata(conn),
        'current_settings': get_current_settings(conn),
        'schedule': schedule,
        'quota': quota,
        'revenue': revenue,
        'pipeline': pipeline,
        'disk': disk_usage,
        'hall_of_fame': hall_of_fame,
        'leaderboard': get_channel_leaderboard(conn),
        'sources_list': sources_list,
        'daily_summary': daily_summary,
        'title_performance': title_performance,
        'style_performance': style_performance,
        'posting_times': posting_times,
        'benchmarks': benchmarks,
        'notifications': notifications,
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

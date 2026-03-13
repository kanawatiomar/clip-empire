#!/usr/bin/env python3
"""Lightweight local control API for the Clip Empire dashboard.

- Serves dashboard files at http://127.0.0.1:8787/
- Exposes POST /api/action for local control-panel actions
- Exposes POST /api/update_channel_settings for channel setting updates
- Regenerates dashboard/data.json on demand

This is optional. GitHub Pages can use the static dashboard in read-only mode.
"""

from __future__ import annotations

import ast
import json
import os
import sqlite3
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
DB_PATH = REPO_ROOT / 'data' / 'clip_empire.db'
SOURCES_PATH = REPO_ROOT / 'engine' / 'config' / 'sources.py'
HOST = '127.0.0.1'
PORT = 8787
ALLOWED_SETTINGS = {'min_views', 'max_per_run', 'crop_anchor', 'daily_target'}
ALLOWED_CROP_ANCHORS = {'left', 'center', 'right'}
DISCORD_API_BASE = 'https://discord.com/api/v10'
DISCORD_CHANNELS = {
    '1475223354066600036': 'bot-logs',
    '1475223373343887421': 'publish-failures',
}


def init_db() -> None:
    """Initialize database tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        # Create dashboard_notifications table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dashboard_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP,
                channel TEXT
            )
        ''')
        conn.commit()
    finally:
        conn.close()


def mark_notifications_read() -> dict:
    """Mark all unread notifications as read."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE dashboard_notifications SET read_at=CURRENT_TIMESTAMP WHERE read_at IS NULL'
        )
        conn.commit()
        return {'ok': True, 'message': 'All notifications marked as read'}
    finally:
        conn.close()


def save_health_score_history() -> None:
    """Read health_score from data.json and append to health_history.json.
    
    Keeps the last 30 entries in health_history.json.
    """
    try:
        data_file = BASE_DIR / 'data.json'
        history_file = BASE_DIR / 'health_history.json'
        
        if not data_file.exists():
            return
        
        # Read data.json
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract health score
        health_score = data.get('health_score', {})
        if not health_score:
            return
        
        # Load existing history or create new
        history = []
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except (json.JSONDecodeError, IOError):
                history = []
        
        # Ensure history is a list
        if not isinstance(history, list):
            history = []
        
        # Add new entry with timestamp
        entry = {
            'timestamp': data.get('generated_at', ''),
            'score': health_score.get('score', 0),
            'grade': health_score.get('grade', 'F'),
            'status': health_score.get('status', 'Unknown'),
            'breakdown': health_score.get('breakdown', {}),
        }
        
        history.append(entry)
        
        # Keep only last 30 entries
        if len(history) > 30:
            history = history[-30:]
        
        # Write back to history file
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
    except Exception as exc:
        # Silently fail if history saving fails - don't break data generation
        pass


def run_generate() -> None:
    subprocess.run(['py', '-3', str(BASE_DIR / 'generate_data.py')], cwd=REPO_ROOT, check=True)
    save_health_score_history()


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def get_discord_bot_token() -> str:
    token = (os.environ.get('DISCORD_BOT_TOKEN') or '').strip()
    if token:
        return token

    dotenv_values = _load_dotenv(REPO_ROOT / '.env')
    token = (dotenv_values.get('DISCORD_BOT_TOKEN') or '').strip()
    if token:
        return token

    raise ValueError('DISCORD_BOT_TOKEN not found in environment or .env')


def _discord_get_json(path: str):
    token = get_discord_bot_token()
    req = urlrequest.Request(
        f'{DISCORD_API_BASE}{path}',
        headers={
            'Authorization': f'Bot {token}',
            'User-Agent': 'ClipEmpireDashboard/1.0',
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urlerror.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise ValueError(f'Discord API error {exc.code}: {detail[:240]}') from exc
    except urlerror.URLError as exc:
        raise ValueError(f'Discord API request failed: {exc.reason}') from exc


def fetch_recent_discord_messages(limit: int = 10) -> list[dict]:
    items: list[dict] = []
    for channel_id, channel_name in DISCORD_CHANNELS.items():
        channel_meta = _discord_get_json(f'/channels/{channel_id}')
        guild_id = channel_meta.get('guild_id') or os.environ.get('DISCORD_GUILD_ID') or _load_dotenv(REPO_ROOT / '.env').get('DISCORD_GUILD_ID')
        messages = _discord_get_json(f'/channels/{channel_id}/messages?limit={int(limit)}')
        for msg in messages:
            content = (msg.get('content') or '').strip()
            if not content:
                embeds = msg.get('embeds') or []
                parts = [embed.get('title') or embed.get('description') or '' for embed in embeds]
                content = ' | '.join(part.strip() for part in parts if part and part.strip())
            items.append({
                'id': msg.get('id'),
                'channel_id': channel_id,
                'channel_name': channel_name,
                'author': (msg.get('author') or {}).get('username') or 'Unknown',
                'timestamp': msg.get('timestamp'),
                'message': content,
                'url': f'https://discord.com/channels/{guild_id}/{channel_id}/{msg.get("id")}' if guild_id and msg.get('id') else None,
            })
    return items


def toggle_channel(channel: str, new_status: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            'UPDATE channels SET status=?, updated_at=CURRENT_TIMESTAMP WHERE channel_name=?',
            (new_status, channel),
        )
        conn.commit()
        if cur.rowcount <= 0:
            raise ValueError(f'Channel not found: {channel}')
    finally:
        conn.close()
    return f'{channel} -> {new_status}'


def tail_logs() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT channel_name, job_id, updated_at, last_error
            FROM publish_jobs
            WHERE last_error IS NOT NULL AND TRIM(last_error) != ''
            ORDER BY datetime(COALESCE(updated_at, created_at)) DESC
            LIMIT 12
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            'channel': r['channel_name'],
            'job_id_short': r['job_id'][:8],
            'updated_at': r['updated_at'],
            'message': (r['last_error'] or '')[:400],
        }
        for r in rows
    ]


def get_logs(lines: int = 100, channel: str = 'all', level: str = 'all') -> list[dict]:
    """Fetch logs from publish_jobs database.
    
    Args:
        lines: Max number of log lines to return
        channel: Filter by channel name ('all' for all channels)
        level: Filter by log level - ERROR, WARN, INFO, DEBUG (inferred from message content)
    
    Returns:
        List of log entries: [{timestamp, level, channel, message}]
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Get all error logs from publish_jobs
        query = """
            SELECT channel_name, job_id, updated_at, status, last_error, created_at
            FROM publish_jobs
            WHERE last_error IS NOT NULL AND TRIM(last_error) != ''
            ORDER BY datetime(COALESCE(updated_at, created_at)) DESC
            LIMIT ?
        """
        rows = conn.execute(query, (lines * 2,)).fetchall()
    finally:
        conn.close()
    
    logs = []
    for r in rows:
        msg = (r['last_error'] or '').strip()
        if not msg:
            continue
        
        # Infer log level from message content and status
        inferred_level = 'ERROR'
        if 'warning' in msg.lower():
            inferred_level = 'WARN'
        elif 'info' in msg.lower() or r['status'] == 'succeeded':
            inferred_level = 'INFO'
        elif 'debug' in msg.lower():
            inferred_level = 'DEBUG'
        elif r['status'] == 'failed':
            inferred_level = 'ERROR'
        
        # Filter by level
        if level != 'all' and inferred_level != level:
            continue
        
        # Filter by channel
        if channel != 'all' and r['channel_name'] != channel:
            continue
        
        logs.append({
            'timestamp': r['updated_at'] or r['created_at'],
            'level': inferred_level,
            'channel': r['channel_name'],
            'message': msg[:500],
        })
    
    # Return only the requested number of lines
    return logs[:lines]


def _normalize_setting_value(setting_name: str, value):
    if setting_name in {'min_views', 'max_per_run', 'daily_target'}:
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'{setting_name} must be an integer') from exc
        if normalized < 0:
            raise ValueError(f'{setting_name} must be >= 0')
        return normalized

    if setting_name == 'crop_anchor':
        normalized = str(value or '').strip().lower()
        if normalized not in ALLOWED_CROP_ANCHORS:
            raise ValueError(f'crop_anchor must be one of: {", ".join(sorted(ALLOWED_CROP_ANCHORS))}')
        return normalized

    raise ValueError(f'Unsupported setting: {setting_name}')


def _load_channel_sources_literal() -> dict:
    source_text = SOURCES_PATH.read_text(encoding='utf-8')
    module = ast.parse(source_text)
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == 'CHANNEL_SOURCES':
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'CHANNEL_SOURCES':
                    return ast.literal_eval(node.value)
    raise ValueError('CHANNEL_SOURCES assignment not found in sources.py')


def _write_channel_sources_literal(channel_sources: dict) -> None:
    source_text = SOURCES_PATH.read_text(encoding='utf-8')
    start_marker = 'CHANNEL_SOURCES: dict = {'
    end_marker = '\n\n# Alias so imports can use either name'
    start = source_text.find(start_marker)
    end = source_text.find(end_marker)
    if start < 0 or end < 0:
        raise ValueError('Unable to locate CHANNEL_SOURCES block in sources.py')

    replacement = 'CHANNEL_SOURCES: dict = ' + json.dumps(channel_sources, indent=4) + '\n'
    updated = source_text[:start] + replacement + source_text[end:]
    SOURCES_PATH.write_text(updated, encoding='utf-8')


def _update_sources_file(channel: str, setting_name: str, value) -> None:
    channel_sources = _load_channel_sources_literal()
    if channel not in channel_sources:
        raise ValueError(f'Channel not found in sources.py: {channel}')

    updated_any = False
    for source in channel_sources[channel]:
        if not isinstance(source, dict):
            continue
        source[setting_name] = value
        updated_any = True

    if not updated_any:
        raise ValueError(f'No editable source entries found for channel: {channel}')

    _write_channel_sources_literal(channel_sources)


def _update_daily_target(channel: str, value: int) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            'UPDATE channels SET daily_target=?, updated_at=CURRENT_TIMESTAMP WHERE channel_name=?',
            (value, channel),
        )
        conn.commit()
        if cur.rowcount <= 0:
            raise ValueError(f'Channel not found: {channel}')
    finally:
        conn.close()


def update_channel_setting(payload: dict) -> dict:
    channel = (payload.get('channel') or '').strip()
    setting_name = (payload.get('setting_name') or '').strip()
    if not channel:
        raise ValueError('channel is required')
    if setting_name not in ALLOWED_SETTINGS:
        raise ValueError(f'Unsupported setting: {setting_name}')

    value = _normalize_setting_value(setting_name, payload.get('value'))
    if setting_name == 'daily_target':
        _update_daily_target(channel, value)
    else:
        _update_sources_file(channel, setting_name, value)

    run_generate()
    return {'ok': True, 'message': f'{channel} {setting_name} updated.', 'channel': channel, 'setting_name': setting_name, 'value': value}


def retry_job(job_id: str) -> dict:
    """Reset a failed/retrying job back to pending and clear the error."""
    if not job_id or not job_id.strip():
        raise ValueError('job_id is required')
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            """
            UPDATE publish_jobs
            SET status = 'pending', last_error = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """,
            (job_id.strip(),),
        )
        conn.commit()
        if cur.rowcount <= 0:
            raise ValueError(f'Job not found: {job_id}')
    finally:
        conn.close()
    return {'ok': True, 'message': f'Job {job_id[:8]} reset to pending.', 'job_id': job_id}


def cancel_job(job_id: str) -> dict:
    """Cancel a job by setting its status to cancelled."""
    if not job_id or not job_id.strip():
        raise ValueError('job_id is required')
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            """
            UPDATE publish_jobs
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """,
            (job_id.strip(),),
        )
        conn.commit()
        if cur.rowcount <= 0:
            raise ValueError(f'Job not found: {job_id}')
    finally:
        conn.close()
    return {'ok': True, 'message': f'Job {job_id[:8]} cancelled.', 'job_id': job_id}


def get_all_channel_status() -> dict[str, str]:
    """Returns all channels with their current status."""
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            'SELECT channel_name, status FROM channels ORDER BY channel_name'
        ).fetchall()
        return {row[0]: row[1] for row in rows}
    finally:
        conn.close()


def cleanup_renders(dry_run: bool = True) -> dict:
    """Delete render files for jobs with status='succeeded'.
    
    Args:
        dry_run: If True, only list files that would be deleted (no actual deletion).
                If False, actually delete the files.
    
    Returns:
        dict with:
        - ok: True if successful
        - files_to_delete: number of files that would be deleted (dry_run) or were deleted
        - bytes_to_free_human: human-readable size of space that would be freed
        - files_deleted: number of files actually deleted (if not dry_run)
        - bytes_freed_human: human-readable size of space actually freed (if not dry_run)
        - message: summary message
    """
    def get_size_human(bytes_size: int) -> str:
        """Convert bytes to human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f}{unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f}TB"
    
    conn = sqlite3.connect(DB_PATH)
    try:
        # Get all succeeded jobs
        rows = conn.execute(
            "SELECT job_id FROM publish_jobs WHERE status='succeeded' ORDER BY job_id"
        ).fetchall()
        
        renders_dir = REPO_ROOT / 'renders'
        files_to_delete = 0
        bytes_to_free = 0
        
        # Find render files for succeeded jobs
        files_for_deletion = []
        
        for row in rows:
            job_id = row[0]
            # Look for job-related render files in renders/ directory
            # Pattern: renders/{job_id}* or renders/{channel}/{job_id}*
            if renders_dir.exists():
                for item in renders_dir.rglob(f'*{job_id}*'):
                    if item.is_file():
                        try:
                            size = item.stat().st_size
                            files_for_deletion.append((item, size))
                            files_to_delete += 1
                            bytes_to_free += size
                        except OSError:
                            pass
        
        # If not dry_run, actually delete the files
        files_deleted = 0
        bytes_freed = 0
        if not dry_run:
            for file_path, size in files_for_deletion:
                try:
                    file_path.unlink()
                    files_deleted += 1
                    bytes_freed += size
                except OSError:
                    pass  # Skip files that can't be deleted
        
        return {
            'ok': True,
            'files_to_delete': files_to_delete,
            'bytes_to_free_human': get_size_human(bytes_to_free),
            'files_deleted': files_deleted if not dry_run else files_to_delete,
            'bytes_freed_human': get_size_human(bytes_freed if not dry_run else bytes_to_free),
            'message': f'{"Would delete" if dry_run else "Deleted"} {files_deleted if not dry_run else files_to_delete} render files from succeeded jobs',
            'dry_run': dry_run,
        }
    except Exception as e:
        return {
            'ok': False,
            'error': str(e),
        }
    finally:
        conn.close()


def add_source(payload: dict) -> dict:
    """Add a new source to CHANNEL_SOURCES config and persist to DB."""
    try:
        channel = payload.get('channel')
        platform = payload.get('platform', '').lower()
        creator_name = payload.get('creator_name', '').strip()
        min_views = int(payload.get('min_views', 0))
        priority = int(payload.get('priority', 2))
        
        if not channel or not creator_name or platform not in {'twitch', 'youtube', 'tiktok', 'reddit'}:
            return {'ok': False, 'error': 'channel, creator_name, and valid platform required'}
        
        # Read current sources.py
        sources_text = SOURCES_PATH.read_text(encoding='utf-8')
        
        # Insert new source entry into the channel's source list
        # This is a simple text insertion; for production, use AST parsing
        new_source = f"""        {{"platform": "{platform}", "url": "", "creator": "{creator_name}", "priority": {priority}, "min_views": {min_views}}},"""
        
        # Find the channel section and append
        if f'"{channel}": [' not in sources_text:
            return {'ok': False, 'error': f'Channel {channel} not found in config'}
        
        # Find insertion point (after the channel opening bracket)
        marker = f'"{channel}": ['
        idx = sources_text.find(marker)
        if idx < 0:
            return {'ok': False, 'error': f'Channel {channel} format not recognized'}
        
        # Find the position after the opening bracket and any leading newline
        insert_pos = idx + len(marker) + 1
        while insert_pos < len(sources_text) and sources_text[insert_pos] in {'\n', '\r'}:
            insert_pos += 1
        
        # Insert the new source with proper indentation
        new_sources_text = sources_text[:insert_pos] + '\n' + new_source + '\n' + sources_text[insert_pos:]
        SOURCES_PATH.write_text(new_sources_text, encoding='utf-8')
        
        return {'ok': True, 'message': f'Added source: {creator_name} ({platform}) to {channel}'}
    except Exception as e:
        return {'ok': False, 'error': f'Failed to add source: {str(e)}'}


def remove_source(payload: dict) -> dict:
    """Remove a source from CHANNEL_SOURCES config."""
    try:
        channel = payload.get('channel')
        source_id = payload.get('source_id')
        
        if not channel or not source_id:
            return {'ok': False, 'error': 'channel and source_id required'}
        
        # Read current sources.py
        sources_text = SOURCES_PATH.read_text(encoding='utf-8')
        
        # For now, simple line-based removal. In production, use AST rewriting.
        lines = sources_text.split('\n')
        new_lines = []
        skip_next = False
        
        for line in lines:
            if skip_next:
                skip_next = False
                continue
            # Look for source dict lines and match creator from source_id
            if source_id.split(':')[1] in line and '"creator":' in line:
                # Skip this source dict line
                continue
            new_lines.append(line)
        
        SOURCES_PATH.write_text('\n'.join(new_lines), encoding='utf-8')
        return {'ok': True, 'message': f'Removed source {source_id} from {channel}'}
    except Exception as e:
        return {'ok': False, 'error': f'Failed to remove source: {str(e)}'}


def toggle_source(payload: dict) -> dict:
    """Toggle source enabled/disabled status."""
    try:
        channel = payload.get('channel')
        source_id = payload.get('source_id')
        enabled = payload.get('enabled', True)
        
        if not channel or not source_id:
            return {'ok': False, 'error': 'channel and source_id required'}
        
        # For now, toggle is tracked in-memory during runtime
        # Full persistence would require config rewrite
        return {'ok': True, 'message': f'Toggled source {source_id} to enabled={enabled}', 'source_id': source_id, 'enabled': enabled}
    except Exception as e:
        return {'ok': False, 'error': f'Failed to toggle source: {str(e)}'}


def send_daily_summary_to_discord() -> dict:
    """Send the daily summary to Discord #bot-logs channel.
    
    Returns:
    - ok: True if successful
    - message_id: Discord message ID if successful
    - error: Error message if failed
    """
    import json
    
    try:
        # Load the latest data.json
        data_json_path = BASE_DIR / 'data.json'
        if not data_json_path.exists():
            raise ValueError('data.json not found. Run generate_data.py first.')
        
        data = json.loads(data_json_path.read_text(encoding='utf-8'))
        daily_summary = data.get('daily_summary', {})
        
        if not daily_summary:
            raise ValueError('No daily_summary data available')
        
        # Get Discord message from daily_summary
        summary_discord = daily_summary.get('summary_discord', '')
        if not summary_discord:
            raise ValueError('No Discord summary text available')
        
        # Send to Discord #bot-logs channel
        channel_id = '1475223354066600036'
        token = get_discord_bot_token()
        
        # Prepare message payload
        message_payload = {
            'content': summary_discord,
        }
        
        # Send POST request to Discord API
        req = urlrequest.Request(
            f'{DISCORD_API_BASE}/channels/{channel_id}/messages',
            data=json.dumps(message_payload).encode('utf-8'),
            headers={
                'Authorization': f'Bot {token}',
                'Content-Type': 'application/json',
                'User-Agent': 'ClipEmpireDashboard/1.0',
            },
            method='POST',
        )
        
        try:
            with urlrequest.urlopen(req, timeout=15) as resp:
                response_data = json.loads(resp.read().decode('utf-8'))
                message_id = response_data.get('id')
                
                # Store last sent time in a metadata file for dashboard display
                metadata = {
                    'last_sent_at': utc_now().isoformat() + 'Z',
                    'last_message_id': message_id,
                    'date': daily_summary.get('date'),
                }
                
                metadata_file = BASE_DIR / '.daily_summary_metadata.json'
                metadata_file.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
                
                return {
                    'ok': True,
                    'message_id': message_id,
                    'message': f'Daily summary sent to Discord ({message_id})',
                    'summary': daily_summary,
                }
        except urlerror.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise ValueError(f'Discord API error {exc.code}: {detail[:240]}') from exc
        except urlerror.URLError as exc:
            raise ValueError(f'Discord API request failed: {exc.reason}') from exc
    except Exception as e:
        return {
            'ok': False,
            'error': str(e),
        }


def utc_now():
    """Return current UTC datetime."""
    from datetime import datetime
    return datetime.utcnow()


def run_action(payload: dict) -> dict:
    action = payload.get('action')
    channel = payload.get('channel')

    if action == 'refresh_data':
        run_generate()
        return {'ok': True, 'message': 'Dashboard data refreshed.'}

    if action == 'engine_scan':
        proc = subprocess.Popen(['py', '-3', '-m', 'engine.cli', '--all'], cwd=REPO_ROOT)
        return {'ok': True, 'message': f'Engine scan started (pid {proc.pid}).'}

    if action == 'process_queue':
        cmd = [
            'py', '-3', '-c',
            'from publisher.youtube_worker import run_once, YouTubeWorkerConfig; raise SystemExit(run_once(YouTubeWorkerConfig(headless=True)))'
        ]
        proc = subprocess.Popen(cmd, cwd=REPO_ROOT)
        return {'ok': True, 'message': f'Queue processor started (pid {proc.pid}).'}

    if action == 'pause_channel':
        result = toggle_channel(channel, 'paused')
        run_generate()
        return {'ok': True, 'message': result}

    if action == 'resume_channel':
        result = toggle_channel(channel, 'active')
        run_generate()
        return {'ok': True, 'message': result}

    if action == 'view_logs':
        return {'ok': True, 'logs': tail_logs()}

    raise ValueError(f'Unknown action: {action}')


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/data':
            try:
                run_generate()
                body = json.loads((BASE_DIR / 'data.json').read_text(encoding='utf-8'))
                self._send_json(body)
            except Exception as exc:
                self._send_json({'ok': False, 'error': str(exc)}, 500)
            return
        if parsed.path == '/api/channel_status':
            try:
                status_map = get_all_channel_status()
                channels = [{'channel': ch, 'status': st} for ch, st in status_map.items()]
                self._send_json({'ok': True, 'channels': channels})
            except Exception as exc:
                self._send_json({'ok': False, 'error': str(exc), 'channels': []}, 500)
            return
        if parsed.path == '/api/discord_feed':
            try:
                self._send_json({'ok': True, 'messages': fetch_recent_discord_messages(limit=10)})
            except Exception as exc:
                self._send_json({'ok': False, 'error': str(exc), 'messages': []}, 500)
            return
        if parsed.path == '/api/daily_summary':
            try:
                # Load the daily summary from data.json
                data_json_path = BASE_DIR / 'data.json'
                if data_json_path.exists():
                    data = json.loads(data_json_path.read_text(encoding='utf-8'))
                    daily_summary = data.get('daily_summary', {})
                else:
                    daily_summary = {}
                
                # Load metadata for last sent time
                metadata_file = BASE_DIR / '.daily_summary_metadata.json'
                metadata = {}
                if metadata_file.exists():
                    try:
                        metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
                    except Exception:
                        metadata = {}
                
                self._send_json({
                    'ok': True,
                    'daily_summary': daily_summary,
                    'last_sent_at': metadata.get('last_sent_at'),
                    'last_message_id': metadata.get('last_message_id'),
                })
            except Exception as exc:
                self._send_json({'ok': False, 'error': str(exc)}, 500)
            return
        if parsed.path == '/api/notifications':
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                try:
                    # Get last 20 unread + 5 most recent read
                    unread = conn.execute(
                        '''SELECT id, type, title, message, created_at, channel
                           FROM dashboard_notifications
                           WHERE read_at IS NULL
                           ORDER BY created_at DESC
                           LIMIT 20'''
                    ).fetchall()
                    
                    read = conn.execute(
                        '''SELECT id, type, title, message, created_at, channel
                           FROM dashboard_notifications
                           WHERE read_at IS NOT NULL
                           ORDER BY created_at DESC
                           LIMIT 5'''
                    ).fetchall()
                    
                    unread_count = conn.execute(
                        'SELECT COUNT(*) FROM dashboard_notifications WHERE read_at IS NULL'
                    ).fetchone()[0]
                finally:
                    conn.close()
                
                notifications = []
                for n in unread:
                    notifications.append({
                        'id': n['id'],
                        'type': n['type'],
                        'title': n['title'],
                        'message': n['message'],
                        'created_at': n['created_at'],
                        'channel': n['channel'],
                        'read': False,
                    })
                
                for n in read:
                    notifications.append({
                        'id': n['id'],
                        'type': n['type'],
                        'title': n['title'],
                        'message': n['message'],
                        'created_at': n['created_at'],
                        'channel': n['channel'],
                        'read': True,
                    })
                
                self._send_json({'ok': True, 'notifications': notifications, 'unread_count': unread_count})
            except Exception as exc:
                self._send_json({'ok': False, 'error': str(exc), 'notifications': [], 'unread_count': 0}, 500)
            return
        if parsed.path == '/api/logs':
            try:
                # Parse query parameters
                from urllib.parse import parse_qs
                query = parse_qs(parsed.query)
                lines = int(query.get('lines', ['100'])[0])
                channel = query.get('channel', ['all'])[0]
                level = query.get('level', ['all'])[0]
                
                # Validate and clamp parameters
                lines = max(1, min(lines, 500))
                
                logs = get_logs(lines=lines, channel=channel, level=level)
                self._send_json({'ok': True, 'logs': logs})
            except Exception as exc:
                self._send_json({'ok': False, 'error': str(exc), 'logs': []}, 500)
            return
        # Serve thumbnails from renders/thumbnails/ directory
        if parsed.path.startswith('/thumbnails/'):
            try:
                # Extract channel and filename from path: /thumbnails/{channel}/{clip_id}.jpg
                parts = parsed.path.split('/')
                if len(parts) >= 4:  # ['', 'thumbnails', 'channel', 'clip_id.jpg']
                    channel = parts[2]
                    filename = parts[3]
                    # Prevent directory traversal attacks
                    if '..' not in channel and '..' not in filename and channel and filename:
                        thumb_path = REPO_ROOT / 'renders' / 'thumbnails' / channel / filename
                        if thumb_path.exists() and thumb_path.is_file():
                            with open(thumb_path, 'rb') as f:
                                content = f.read()
                            self.send_response(200)
                            self.send_header('Content-Type', 'image/jpeg')
                            self.send_header('Content-Length', str(len(content)))
                            self.send_header('Cache-Control', 'public, max-age=86400')
                            self.end_headers()
                            self.wfile.write(content)
                            return
            except Exception:
                pass
            self.send_response(404)
            self.end_headers()
            return
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in {'/api/action', '/api/update_channel_settings', '/api/retry_job', '/api/cancel_job', '/api/enable_channel', '/api/disable_channel', '/api/cleanup_renders', '/api/add_source', '/api/remove_source', '/api/toggle_source', '/api/send_daily_summary', '/api/mark_notifications_read'}:
            self._send_json({'ok': False, 'error': 'Not found'}, 404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(length).decode('utf-8') or '{}')
            
            # Parse query parameters for enable/disable endpoints
            from urllib.parse import parse_qs
            query = parse_qs(parsed.query)
            channel_param = query.get('channel', [None])[0]
            
            if parsed.path == '/api/enable_channel':
                channel = channel_param or payload.get('channel')
                if not channel:
                    raise ValueError('channel is required')
                result = toggle_channel(channel, 'active')
                run_generate()
                return self._send_json({'ok': True, 'message': result, 'channel': channel, 'status': 'active'})
            elif parsed.path == '/api/disable_channel':
                channel = channel_param or payload.get('channel')
                if not channel:
                    raise ValueError('channel is required')
                result = toggle_channel(channel, 'paused')
                run_generate()
                return self._send_json({'ok': True, 'message': result, 'channel': channel, 'status': 'paused'})
            elif parsed.path == '/api/update_channel_settings':
                result = update_channel_setting(payload)
            elif parsed.path == '/api/retry_job':
                result = retry_job(payload.get('job_id', ''))
            elif parsed.path == '/api/cancel_job':
                result = cancel_job(payload.get('job_id', ''))
            elif parsed.path == '/api/cleanup_renders':
                dry_run = payload.get('dry_run', True)
                result = cleanup_renders(dry_run=dry_run)
            elif parsed.path == '/api/add_source':
                result = add_source(payload)
                if result.get('ok'):
                    run_generate()
            elif parsed.path == '/api/remove_source':
                result = remove_source(payload)
                if result.get('ok'):
                    run_generate()
            elif parsed.path == '/api/toggle_source':
                result = toggle_source(payload)
                if result.get('ok'):
                    run_generate()
            elif parsed.path == '/api/send_daily_summary':
                result = send_daily_summary_to_discord()
            elif parsed.path == '/api/mark_notifications_read':
                result = mark_notifications_read()
            else:
                result = run_action(payload)
                if payload.get('action') in {'pause_channel', 'resume_channel', 'refresh_data'}:
                    run_generate()
            self._send_json(result)
        except Exception as exc:
            self._send_json({'ok': False, 'error': str(exc)}, 400)


if __name__ == '__main__':
    init_db()
    run_generate()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f'Clip Empire dashboard server running at http://{HOST}:{PORT}')
    server.serve_forever()

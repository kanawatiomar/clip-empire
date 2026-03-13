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


def run_generate() -> None:
    subprocess.run(['py', '-3', str(BASE_DIR / 'generate_data.py')], cwd=REPO_ROOT, check=True)


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
        return {'ok': True, 'message': toggle_channel(channel, 'paused')}

    if action == 'resume_channel':
        return {'ok': True, 'message': toggle_channel(channel, 'active')}

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
        if parsed.path == '/api/discord_feed':
            try:
                self._send_json({'ok': True, 'messages': fetch_recent_discord_messages(limit=10)})
            except Exception as exc:
                self._send_json({'ok': False, 'error': str(exc), 'messages': []}, 500)
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
        if parsed.path not in {'/api/action', '/api/update_channel_settings', '/api/retry_job', '/api/cancel_job'}:
            self._send_json({'ok': False, 'error': 'Not found'}, 404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(length).decode('utf-8') or '{}')
            
            if parsed.path == '/api/update_channel_settings':
                result = update_channel_setting(payload)
            elif parsed.path == '/api/retry_job':
                result = retry_job(payload.get('job_id', ''))
            elif parsed.path == '/api/cancel_job':
                result = cancel_job(payload.get('job_id', ''))
            else:
                result = run_action(payload)
                if payload.get('action') in {'pause_channel', 'resume_channel', 'refresh_data'}:
                    run_generate()
            self._send_json(result)
        except Exception as exc:
            self._send_json({'ok': False, 'error': str(exc)}, 400)


if __name__ == '__main__':
    run_generate()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f'Clip Empire dashboard server running at http://{HOST}:{PORT}')
    server.serve_forever()

#!/usr/bin/env python3
"""Lightweight local control API for the Clip Empire dashboard.

- Serves dashboard files at http://127.0.0.1:8787/
- Exposes POST /api/action for local control-panel actions
- Regenerates dashboard/data.json on demand

This is optional. GitHub Pages can use the static dashboard in read-only mode.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
DB_PATH = REPO_ROOT / 'data' / 'clip_empire.db'
HOST = '127.0.0.1'
PORT = 8787


def run_generate() -> None:
    subprocess.run(['py', '-3', str(BASE_DIR / 'generate_data.py')], cwd=REPO_ROOT, check=True)


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
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/action':
            self._send_json({'ok': False, 'error': 'Not found'}, 404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(length).decode('utf-8') or '{}')
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

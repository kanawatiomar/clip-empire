
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import json
import time

from data.migrate import ensure_schema

# Assuming DATABASE_PATH is defined in data/schema.py or similar
DATABASE_PATH = "data/clip_empire.db"

# Helper function to convert row to dictionary
def _row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(zip([col[0] for col in cursor.description], row))
    if 'hashtags' in data and isinstance(data['hashtags'], str):
        try:
            data['hashtags'] = json.loads(data['hashtags'])
        except json.JSONDecodeError:
            data['hashtags'] = [] # Default to empty list if decode fails
    return data

def get_db_connection():
    # Ensure schema is up-to-date before any DB operations
    ensure_schema(DATABASE_PATH)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _to_utc_epoch_seconds(dt: datetime) -> int:
    """Convert datetime to UTC epoch seconds.

    - If dt is naive, assume it's local time.
    - If dt is aware, convert to UTC.
    """
    if dt.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        dt = dt.replace(tzinfo=local_tz)
    return int(dt.astimezone(timezone.utc).timestamp())

def add_publish_job(
    variant_id: str,
    platform: str,
    channel_name: str,
    publisher_account: str,
    schedule_at: datetime,
    caption_text: str,
    hashtags: List[str],
    render_path: str,
    first_frame_hook: Optional[str] = None
) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    job_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    updated_at = created_at

    # Ensure hashtags are stored as a JSON string
    hashtags_json = json.dumps(hashtags)

    try:
        schedule_at_ts = _to_utc_epoch_seconds(schedule_at)

        cursor.execute("""
            INSERT INTO publish_jobs (
                job_id, variant_id, platform, channel_name, publisher_account, 
                schedule_at, schedule_at_ts, created_at, updated_at,
                caption_text, hashtags, render_path, first_frame_hook
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id, variant_id, platform, channel_name, publisher_account,
            schedule_at.isoformat(), schedule_at_ts,
            created_at, updated_at,
            caption_text, hashtags_json, render_path, first_frame_hook
        ))
        conn.commit()
        print(f"Added publish job {job_id} for {channel_name} on {platform}.")
        return job_id
    except sqlite3.Error as e:
        print(f"Error adding publish job: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def get_next_job(platform: str, channel_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_ts = int(time.time())

    # Select a job that is queued, scheduled for now or past, and ready for retry.
    # Use numeric epoch seconds to avoid timezone/string-compare bugs.
    query = """
        SELECT pj.*, c.made_for_kids FROM publish_jobs pj
        JOIN channels c ON pj.channel_name = c.channel_name
        WHERE pj.status = 'queued'
          AND c.status = 'active'
          AND pj.platform = ?
          AND (pj.schedule_at_ts IS NULL OR pj.schedule_at_ts <= ?)
          AND (pj.next_retry_at_ts IS NULL OR pj.next_retry_at_ts <= ?)
    """
    params = (platform, now_ts, now_ts)

    if channel_name:
        query += " AND pj.channel_name = ?"
        params += (channel_name,)
    
    # Add render_path, caption_text, hashtags, first_frame_hook to the SELECT statement from publish_jobs table
    # if they are not already in the table definition
    # Assuming they are already in publish_jobs table as per the original schema idea. 
    
    query += " ORDER BY attempts ASC, COALESCE(schedule_at_ts, 0) ASC LIMIT 1"

    try:
        cursor.execute(query, params)
        job_row = cursor.fetchone()
        if job_row:
            job = _row_to_dict(cursor, job_row)
            # Optimistically mark as running to prevent other workers picking it up
            cursor.execute("UPDATE publish_jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                           ('running', datetime.now().isoformat(), job['job_id']))
            conn.commit()
            print(f"Fetched and marked job {job['job_id']} as running.")
            return job
        return None
    except sqlite3.Error as e:
        print(f"Error getting next publish job: {e}")
        raise
    finally:
        conn.close()

def update_job_status(job_id: str, status: str, post_url: Optional[str] = None,
                      platform_post_id: Optional[str] = None) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    updated_at = datetime.now().isoformat()

    try:
        cursor.execute("""
            UPDATE publish_jobs 
            SET status = ?, updated_at = ? 
            WHERE job_id = ?
        """, (status, updated_at, job_id))
        
        # If job succeeded, log the result
        if status == 'succeeded':
            result_id = str(uuid.uuid4())
            started_at = updated_at # Simplification, actual start time should be passed
            finished_at = updated_at
            success = True
            cursor.execute("""
                INSERT INTO publish_results (
                    result_id, job_id, started_at, finished_at, success, post_url, platform_post_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (result_id, job_id, started_at, finished_at, success, post_url, platform_post_id))

        conn.commit()
        print(f"Updated publish job {job_id} status to {status}.")
    except sqlite3.Error as e:
        print(f"Error updating publish job status: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def fail_job(job_id: str, error_class: str, error_detail: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    updated_at = datetime.now().isoformat()

    try:
        cursor.execute("UPDATE publish_jobs SET attempts = attempts + 1, updated_at = ? WHERE job_id = ?",
                       (updated_at, job_id))
        
        # Get current attempts to calculate next_retry_at with exponential backoff
        cursor.execute("SELECT attempts FROM publish_jobs WHERE job_id = ?", (job_id,))
        current_attempts = cursor.fetchone()['attempts']
        
        # Exponential backoff (e.g., 2m, 10m, 45m for attempts 1, 2, 3)
        if current_attempts == 1:
            retry_after_minutes = 2
        elif current_attempts == 2:
            retry_after_minutes = 10
        elif current_attempts == 3:
            retry_after_minutes = 45
        else:
            retry_after_minutes = 0 # No more retries after 3 failures
            # If attempts > 3, set status to failed and don't schedule retry
            cursor.execute("UPDATE publish_jobs SET status = ?, next_retry_at = NULL, updated_at = ? WHERE job_id = ?",
                           ('failed', updated_at, job_id))
            conn.commit()
            print(f"Publish job {job_id} permanently failed after {current_attempts} attempts.")
            return

        next_retry_dt = datetime.now().astimezone(timezone.utc) + timedelta(minutes=retry_after_minutes)
        next_retry_at = next_retry_dt.isoformat()
        next_retry_at_ts = int(next_retry_dt.timestamp())
        
        cursor.execute("""
            UPDATE publish_jobs 
            SET status = 'queued', last_error = ?, next_retry_at = ?, next_retry_at_ts = ?, updated_at = ? 
            WHERE job_id = ?
        """, (error_detail, next_retry_at, next_retry_at_ts, updated_at, job_id))

        # Log the failure in publish_results
        result_id = str(uuid.uuid4())
        started_at = updated_at # Simplification
        finished_at = updated_at
        success = False
        cursor.execute("""
            INSERT INTO publish_results (
                result_id, job_id, started_at, finished_at, success, error_class, error_detail
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (result_id, job_id, started_at, finished_at, success, error_class, error_detail))

        conn.commit()
        print(f"Publish job {job_id} failed. Retrying in {retry_after_minutes} minutes.")

    except sqlite3.Error as e:
        print(f"Error failing publish job: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    # Example usage (requires data/clip_empire.db to be initialized and channels/platform_variants tables to have data)
    print("--- Testing publisher/queue.py ---")
    
    # Add a dummy channel for testing if it doesn't exist
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO channels (channel_name, category, created_at, updated_at) VALUES (?, ?, ?, ?)",
                       ('test_channel', 'experimental', datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding dummy channel: {e}")
    finally:
        conn.close()

    # Add a dummy platform variant for testing if it doesn't exist
    # This part is more complex as it requires foreign keys from segments and clip_assets
    # For a quick test, we'll skip full variant creation and just provide dummy variant_id directly
    dummy_variant_id = str(uuid.uuid4())
    
    # Try adding a job
    try:
        job_id_1 = add_publish_job(
            variant_id=dummy_variant_id,
            platform='youtube',
            channel_name='test_channel',
            publisher_account='youtube:test_channel',
            schedule_at=datetime.now() - timedelta(minutes=1),
            caption_text="Test Caption 1",
            hashtags=["test", "youtube"],
            render_path="renders/youtube/test_channel/test_render.mp4"
        )
        print(f"Test Job 1 ID: {job_id_1}")
    except Exception as e:
        print(f"Failed to add job 1: {e}")

    # Get next job
    next_job = get_next_job('youtube', 'test_channel')
    if next_job:
        print(f"Fetched Job: {next_job['job_id']} with status {next_job['status']}")
        # Simulate success
        update_job_status(next_job['job_id'], 'succeeded', 'https://youtube.com/test', 'yt12345')
        
        # Try getting next job again, should be None
        next_job_after_success = get_next_job('youtube', 'test_channel')
        print(f"Next job after success (should be None): {next_job_after_success}")
    else:
        print("No job fetched (expected if already succeeded).")

    # Add another job to test failure
    dummy_variant_id_2 = str(uuid.uuid4())
    try:
        job_id_2 = add_publish_job(
            variant_id=dummy_variant_id_2,
            platform='youtube',
            channel_name='test_channel',
            publisher_account='youtube:test_channel',
            schedule_at=datetime.now() - timedelta(minutes=2),
            caption_text="Test Caption 2",
            hashtags=["test2", "youtube2"],
            render_path="renders/youtube/test_channel/test_render2.mp4"
        )
        print(f"Test Job 2 ID: {job_id_2}")
    except Exception as e:
        print(f"Failed to add job 2: {e}")

    # Get and fail job twice
    for i in range(1, 4):
        job_to_fail = get_next_job('youtube', 'test_channel')
        if job_to_fail:
            print(f"Attempt {i}: Failing Job {job_to_fail['job_id']}")
            fail_job(job_to_fail['job_id'], 'network_error', f'Simulated network failure {i}')
            time.sleep(1) # Wait a bit for next retry window in test
        else:
            print(f"No job to fail on attempt {i} (expected after permanent failure).")

    print("--- publisher/queue.py tests complete ---")

#!/usr/bin/env python3
"""
Batch sync YouTube analytics for all configured channels.
Usage: python sync_all.py
Can be run manually or via Task Scheduler
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

CHANNELS = [
    'arc_highlightz',
    'fomo_highlights',
    'market_meltdowns',
    'viral_recaps',
]

def sync_all():
    """Sync analytics for all channels that have tokens."""
    print(f"\n{'='*60}")
    print(f"YouTube Analytics Sync - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    analytics_dir = Path(__file__).parent
    results = []
    
    for channel in CHANNELS:
        token_path = analytics_dir / 'tokens' / f'{channel}.pickle'
        
        if not token_path.exists():
            print(f"[{channel}] ⊘ Token not found - skipping")
            print(f"         Run: python auth_setup.py {channel}")
            continue
        
        print(f"[{channel}] Syncing...")
        
        try:
            result = subprocess.run(
                [sys.executable, str(analytics_dir / 'youtube_analytics.py'), channel],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per channel
            )
            
            if result.returncode == 0:
                # Extract summary from output
                output = result.stdout
                # Look for "updated X videos" pattern
                import re
                match = re.search(r'Updated (\d+) videos', output)
                if match:
                    count = match.group(1)
                    print(f"         ✓ Synced {count} videos")
                else:
                    print(result.stdout)
                results.append((channel, True, result.stdout))
            else:
                print(f"         ✗ Error: {result.stderr}")
                results.append((channel, False, result.stderr))
        
        except subprocess.TimeoutExpired:
            print(f"         ✗ Timeout after 5 minutes")
            results.append((channel, False, "Timeout"))
        except Exception as e:
            print(f"         ✗ Exception: {e}")
            results.append((channel, False, str(e)))
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    success_count = sum(1 for _, success, _ in results if success)
    print(f"Completed: {success_count}/{len(results)} channels")
    
    if results:
        for channel, success, msg in results:
            status = "✓" if success else "✗"
            print(f"  {status} {channel}")
    
    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return success_count == len(results)

if __name__ == '__main__':
    success = sync_all()
    sys.exit(0 if success else 1)

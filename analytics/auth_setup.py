#!/usr/bin/env python3
"""
One-time OAuth setup for YouTube Analytics per channel.
Usage: python auth_setup.py arc_highlightz
"""

import sys
import os
import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# Channel to credentials mapping
CHANNEL_CREDENTIALS = {
    'arc_highlightz': 'client_secrets_main.json',
    'fomo_highlights': 'client_secrets_main.json',
    'market_meltdowns': 'client_secrets_main.json',
    'viral_recaps': 'client_secrets_viral.json',
}

SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']

def get_youtube_token(channel_name):
    """Get OAuth token for YouTube API access."""
    if channel_name not in CHANNEL_CREDENTIALS:
        print(f"Error: Channel '{channel_name}' not recognized")
        print(f"Supported channels: {', '.join(CHANNEL_CREDENTIALS.keys())}")
        sys.exit(1)
    
    # Get credentials file
    creds_file = CHANNEL_CREDENTIALS[channel_name]
    creds_path = Path(__file__).parent / creds_file
    
    if not creds_path.exists():
        print(f"Error: Credentials file not found: {creds_path}")
        sys.exit(1)
    
    # Create tokens directory if needed
    tokens_dir = Path(__file__).parent / 'tokens'
    tokens_dir.mkdir(exist_ok=True)
    
    # Token file path
    token_path = tokens_dir / f'{channel_name}.pickle'
    
    # Create flow and run authentication
    print(f"\n[{channel_name}] Starting OAuth authentication...")
    print(f"Using credentials: {creds_file}")
    print("\nOpening browser for consent screen...")
    
    flow = InstalledAppFlow.from_client_secrets_file(
        str(creds_path),
        scopes=SCOPES,
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'
    )
    
    creds = flow.run_local_server(port=0)
    
    # Save token
    with open(token_path, 'wb') as token_file:
        pickle.dump(creds, token_file)
    
    print(f"\n✓ Token saved to: {token_path}")
    print(f"✓ Channel '{channel_name}' is ready for analytics sync!")
    return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python auth_setup.py <channel_name>")
        print(f"Supported channels: {', '.join(CHANNEL_CREDENTIALS.keys())}")
        sys.exit(1)
    
    channel_name = sys.argv[1]
    try:
        get_youtube_token(channel_name)
    except Exception as e:
        print(f"\nError during authentication: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

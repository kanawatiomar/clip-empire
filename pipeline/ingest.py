
import os
import uuid
from datetime import datetime
from pipeline.schemas import Source

# Placeholder for a real download function
def download_source_video(url: str, source_type: str, creator: str, title: str) -> Source:
    source_id = str(uuid.uuid4())
    download_path = os.path.join("ingest", f"{source_id}.mp4")

    # Simulate a download by creating a dummy file
    os.makedirs(os.path.dirname(download_path), exist_ok=True)
    with open(download_path, 'w') as f:
        f.write("dummy video content")

    print(f"Simulated download of {url} to {download_path}")

    return Source(
        source_id=source_id,
        type=source_type,
        url=url,
        creator=creator,
        title=title,
        download_path=download_path,
        duration_s=600.0,  # Dummy duration
        ingested_at=datetime.now().isoformat()
    )

if __name__ == '__main__':
    # Example usage
    dummy_url = "https://www.youtube.com/watch?v=dummy_video"
    dummy_source = download_source_video(dummy_url, "youtube_video", "DummyCreator", "A Dummy Video")
    print(f"Created dummy source: {dummy_source}")

#!/usr/bin/env python3
"""
YouTube Transcript Fetcher - Improved version with:
- Hybrid approach: Try youtube-transcript-api first (fast), fall back to yt-dlp (reliable)
- Auto-installation of dependencies if missing
- Progress updates for bot/agent visibility
- Streaming output for better timeout recovery
- Video duration pre-check
- Graceful error handling
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Progress markers that the bot can parse
PROGRESS_PREFIX = ">>>PROGRESS:"
ERROR_PREFIX = ">>>ERROR:"
INFO_PREFIX = ">>>INFO:"

# YouTube URL patterns to extract video ID
YT_ID_PATTERNS = [
    r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
    r'(?:embed\/)([0-9A-Za-z_-]{11})',
    r'(?:v\/)([0-9A-Za-z_-]{11})',
]

def log_progress(message: str):
    """Log progress in a machine-readable format"""
    print(f"{PROGRESS_PREFIX} {message}", file=sys.stderr, flush=True)

def log_error(message: str):
    """Log error in a machine-readable format"""
    print(f"{ERROR_PREFIX} {message}", file=sys.stderr, flush=True)

def log_info(message: str):
    """Log info in a machine-readable format"""
    print(f"{INFO_PREFIX} {message}", file=sys.stderr, flush=True)

def extract_video_id(url: str) -> str | None:
    """Extract video ID from YouTube URL"""
    for pattern in YT_ID_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def ensure_youtube_transcript_api_installed() -> bool:
    """Check if youtube-transcript-api is installed, install if missing"""
    log_progress("Checking if youtube-transcript-api is installed...")

    try:
        import youtube_transcript_api
        log_info(f"youtube-transcript-api found")
        return True
    except ImportError:
        pass

    log_progress("youtube-transcript-api not found, installing via pip...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "youtube-transcript-api", "--quiet"],
            check=True,
            timeout=120
        )
        log_info("Successfully installed youtube-transcript-api")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log_error(f"Failed to install youtube-transcript-api: {e}")
        return False

def get_transcript_via_api(video_id: str) -> str | None:
    """Fetch transcript using youtube-transcript-api (fast method)"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, VideoUnavailable

        log_progress("Fetching transcript via API (fast method)...")

        # Try to get transcript, preferring manually created ones
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except NoTranscriptFound:
            # Try auto-generated transcripts
            log_info("No manual transcript found, trying auto-generated...")
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_manually_created_transcript()
            if not transcript:
                transcript = transcript_list.find_generated_transcript()
            if transcript:
                transcript = transcript.fetch()

        # Format: combine text with spacing
        text_lines = []
        for entry in transcript:
            text = entry.get("text", "").strip()
            if text:
                text_lines.append(text)

        result = " ".join(text_lines)
        log_info(f"API fetch successful: {len(result)} characters")
        return result

    except (NoTranscriptFound, TranscriptsDisabled):
        log_info("No transcript available via API")
        return None
    except VideoUnavailable:
        log_info("Video unavailable via API")
        return None
    except Exception as e:
        log_info(f"API fetch failed: {type(e).__name__}")
        return None

def ensure_yt_dlp_installed() -> bool:
    """Check if yt-dlp is installed, install if missing"""
    log_progress("Checking if yt-dlp is installed...")

    # Check if yt-dlp exists
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.decode().strip()
            log_info(f"yt-dlp version {version} found")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Not found, try to install
    log_progress("yt-dlp not found, installing via pip...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "yt-dlp", "--quiet"],
            check=True,
            timeout=120
        )
        log_info("Successfully installed yt-dlp")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log_error(f"Failed to install yt-dlp: {e}")
        log_error("Please install manually: pip install yt-dlp")
        return False

def get_video_info(url: str) -> dict:
    """Get video information including duration"""
    log_progress("Fetching video info...")
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        url
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=60,
            text=True
        )
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return info
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    return {}

def clean_vtt(content: str) -> str:
    """
    Clean WebVTT content to plain text.
    Removes headers, timestamps, and duplicate lines.
    """
    lines = content.splitlines()
    text_lines = []

    timestamp_pattern = re.compile(r'\d{2}:\d{2}:\d{2}\.\d{3}\s-->\s\d{2}:\d{2}:\d{2}\.\d{3}')

    for line in lines:
        line = line.strip()
        if not line or line == 'WEBVTT' or line.isdigit():
            continue
        if timestamp_pattern.match(line):
            continue
        if line.startswith('NOTE') or line.startswith('STYLE'):
            continue

        if text_lines and text_lines[-1] == line:
            continue

        line = re.sub(r'<[^>]+>', '', line)

        text_lines.append(line)

    return '\n'.join(text_lines)

def calculate_timeout(duration_seconds: int) -> int:
    """Calculate appropriate timeout based on video duration"""
    # Base timeout + additional time per minute of video
    base_timeout = 60  # 1 minute minimum
    per_minute = 5  # 5 seconds per minute of video
    calculated = base_timeout + (duration_seconds // 60) * per_minute
    # Cap at 15 minutes maximum
    return min(calculated, 900)

def get_transcript(url: str, timeout_override: int = 0):
    """Fetch and print transcript with progress updates (hybrid approach)"""

    # Step 1: Try the fast API method first
    video_id = extract_video_id(url)
    if video_id and ensure_youtube_transcript_api_installed():
        api_result = get_transcript_via_api(video_id)
        if api_result:
            log_progress(f"Streaming transcript ({len(api_result)} characters)...")
            print(api_result, flush=True)
            log_progress(f"Done! Fetched {len(api_result)} characters via API")
            return  # Success - exit early
        log_info("API method failed, falling back to yt-dlp...")

    # Step 2: Fall back to yt-dlp (slower but more reliable)
    log_progress("Using yt-dlp fallback method...")

    # Ensure yt-dlp is installed
    if not ensure_yt_dlp_installed():
        sys.exit(2)  # Exit code 2 = dependency missing

    # Get video info for duration-based timeout
    video_info = get_video_info(url)
    duration = 0
    if video_info:
        duration = video_info.get('duration', 0)
        title = video_info.get('title', 'Unknown')
        log_info(f"Video: {title}")

    # Calculate timeout and warn user for long videos
    if timeout_override > 0:
        timeout = timeout_override
        log_info(f"Using custom timeout: {timeout} seconds")
    else:
        timeout = calculate_timeout(duration)

    if duration > 3600:  # 1+ hour
        log_error(f"WARNING: Very long video detected ({duration//60} minutes)")
        log_error(f"Transcript fetch may take several minutes. Timeout set to {timeout} seconds.")
    elif duration > 1800:  # 30+ minutes
        log_error(f"WARNING: Long video detected ({duration//60} minutes)")
        log_error(f"Transcript fetch may take 1-2 minutes. Timeout set to {timeout} seconds.")
    elif duration > 600:  # 10+ minutes
        log_info(f"Medium-length video ({duration//60} minutes). Timeout: {timeout} seconds")

    # Fetch transcript via yt-dlp
    log_progress("Fetching transcript via yt-dlp...")

    with tempfile.TemporaryDirectory() as temp_dir:
        cmd = [
            "yt-dlp",
            "--write-subs",
            "--write-auto-subs",
            "--skip-download",
            "--sub-lang", "en",
            "--output", "subs",
            url
        ]

        try:
            # Run without capturing output so we see real-time errors
            result = subprocess.run(
                cmd,
                cwd=temp_dir,
                check=True,
                capture_output=True,
                timeout=timeout
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if e.stderr else "Unknown error"
            log_error(f"Failed to fetch transcript: {stderr[:500]}")
            sys.exit(3)  # Exit code 3 = fetch failed
        except subprocess.TimeoutExpired:
            log_error(f"Transcript fetch timed out after {timeout} seconds.")
            log_error(f"Try again with --timeout {timeout * 2} for more time")
            sys.exit(124)  # Standard timeout exit code
        except FileNotFoundError:
            log_error("yt-dlp not found. This should not happen after auto-install.")
            sys.exit(2)

        # Step 4: Process and stream transcript
        log_progress("Processing transcript...")

        temp_path = Path(temp_dir)
        vtt_files = list(temp_path.glob("*.vtt"))

        if not vtt_files:
            log_error("No subtitles found for this video")
            sys.exit(4)  # Exit code 4 = no subtitles

        # Use the first VTT file (usually English)
        vtt_file = vtt_files[0]

        # Read in chunks for very large files
        content = vtt_file.read_text(encoding='utf-8')
        clean_text = clean_vtt(content)

        # Stream output immediately so it's available even if timeout occurs
        log_progress(f"Streaming transcript ({len(clean_text)} characters)...")
        print(clean_text, flush=True)

        log_progress(f"Done! Fetched {len(clean_text)} characters")

def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube transcript.")
    parser.add_argument("url", help="YouTube video URL", nargs='?')
    parser.add_argument("--smoke-test", action="store_true", help="Run smoke test for onboarding")
    parser.add_argument("--timeout", type=int, default=0, help="Override timeout in seconds (0 = auto)")
    args = parser.parse_args()

    if args.smoke_test:
        print("OK")
        return

    if not args.url:
        parser.error("the following arguments are required: url")

    try:
        get_transcript(args.url, args.timeout)
    except KeyboardInterrupt:
        log_error("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

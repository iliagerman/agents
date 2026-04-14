---
name: youtube-watcher
description: Fetch and read transcripts from YouTube videos. Use when you need to summarize a video, answer questions about its content, or extract information from it.
author: michael gathara
version: 1.1.0
triggers:
  - "watch youtube"
  - "summarize video"
  - "video transcript"
  - "youtube summary"
  - "analyze video"
metadata: {"clawdbot":{"emoji":"📺","install":[{"id":"pip","kind":"pip","package":"yt-dlp","bins":["yt-dlp"],"label":"Install yt-dlp (pip)"},{"id":"pip","kind":"pip","package":"youtube-transcript-api","label":"Install youtube-transcript-api (pip)"}]}}
---

# YouTube Watcher

Fetch transcripts from YouTube videos to enable summarization, QA, and content extraction.

## How To Use This Skill

**CRITICAL:** Read this section carefully before running any commands.

1. The script is located at `scripts/get_transcript.py` inside this skill directory
2. There is NO file named `youtube_watcher.py` — do not attempt to run it
3. You MUST pass a YouTube URL as the first argument to the script
4. The script uses a **hybrid approach**: tries fast API first, falls back to yt-dlp if needed
5. Both dependencies auto-install if missing

**Correct command format:**
```bash
shell(command="python3 {baseDir}/scripts/get_transcript.py 'https://www.youtube.com/watch?v=VIDEO_ID'", timeout_seconds=300)
```

**Wrong — do NOT use:**
```bash
uv run youtube_watcher.py          # This file does not exist
python youtube_watcher.py          # This file does not exist
get_transcript.py                  # Missing path and URL
```

## Usage

### Get Transcript

Retrieve the text transcript of a video.

```bash
python3 {baseDir}/scripts/get_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

**Hybrid Approach:** The script first tries `youtube-transcript-api` (typically 1-2 seconds). If that fails, it falls back to `yt-dlp` (slower but more reliable).

**Timeout:** For long videos (>30 min), use `--timeout` or the script will auto-calculate based on video length:

```bash
# Auto timeout (recommended)
python3 {baseDir}/scripts/get_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Custom timeout
python3 {baseDir}/scripts/get_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID" --timeout 600
```

### Progress Updates

The script now outputs progress updates to stderr that you can monitor:
- `>>>PROGRESS: message` - Progress updates
- `>>>INFO: message` - Informational messages
- `>>>ERROR: message` - Error messages

**Recommended:** Watch stderr for progress and communicate updates to the user during long-running fetches.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Unexpected error |
| 2 | Dependency missing (yt-dlp could not be installed) |
| 3 | Fetch failed (video not found, no captions, etc.) |
| 4 | No subtitles available for this video |
| 124 | Timeout exceeded |
| 130 | Interrupted by user |

## Examples

**Summarize a video:**

1. Get the transcript (always use timeout_seconds=300 or higher):
   ```bash
   timeout_seconds=300 python3 {baseDir}/scripts/get_transcript.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
   ```
2. Read the output and summarize it for the user.

**Find specific information:**

1. Get the transcript (use timeout_seconds=300 or higher):
   ```bash
   timeout_seconds=300 python3 {baseDir}/scripts/get_transcript.py "https://www.youtube.com/watch?v=VIDEO_ID"
   ```
2. Search the text for keywords or answer the user's question based on the content.

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `youtube_watcher.py: No such file or directory` | You're using the wrong filename | Use `scripts/get_transcript.py` instead |
| `the following arguments are required: url` | You forgot to pass the YouTube URL | Add the URL as the first argument |
| `command timed out` | Video is very long, timeout exceeded | Re-run with `--timeout 1200` or higher |
| `API method failed, falling back to yt-dlp` | Fast API unavailable, using slow method | Normal fallback, will take longer |
| `No transcript available via API` | API couldn't fetch, using yt-dlp fallback | Normal fallback, will take longer |
| `This video does not have subtitles` | Video has no captions/transcript | Inform the user the video cannot be transcribed |
| `>>>ERROR: Failed to fetch transcript` | Video is private, region-locked, or unavailable | Inform the user of the issue |

## Notes

- **Hybrid approach:** Tries fast `youtube-transcript-api` first (~1-2 sec), falls back to `yt-dlp` if needed (~5-30 sec)
- **Auto-installation:** Both dependencies auto-install via pip if missing
- **No credentials required:** Works with public YouTube videos without API keys
- Works with videos that have closed captions (CC) or auto-generated subtitles
- If a video has no subtitles, the script will fail with exit code 4
- **Dynamic timeout:** Automatically calculates timeout based on video length (max 15 min)
- **Progress:** Monitor stderr for `>>>PROGRESS:` messages to keep user informed

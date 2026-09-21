---
name: gemini-deep-research
description: Perform complex, long-running research tasks using Gemini Deep Research Agent. Use when asked to research topics requiring multi-source synthesis, competitive analysis, market research, or comprehensive technical investigations that benefit from systematic web search and analysis.
metadata: {"clawdbot":{"emoji":"🔬","requires":{"env":["GEMINI_API_KEY"]},"primaryEnv":"GEMINI_API_KEY"}}
requires:
  env:
    - name: GEMINI_API_KEY
      prompt: "Provide your Gemini API key for Gemini Deep Research (it will be stored in skills_secrets.yml and used for research calls)."
      example: "AIzaSy..."
  pip:
    - requests
---

# Gemini Deep Research

Use Gemini's Deep Research Agent to perform complex, long-running context gathering and synthesis tasks.

## Prerequisites

- `GEMINI_API_KEY` environment variable (from Google AI Studio)
- **Note**: This does NOT work with Antigravity OAuth tokens. Requires a direct Gemini API key.

### Python dependencies

Install required packages with uv:

```bash
uv pip install requests
```

## How It Works

Deep Research is an agent that:
1. Breaks down complex queries into sub-questions
2. Searches the web systematically
3. Synthesizes findings into comprehensive reports
4. Provides streaming progress updates

## Usage

### Portable paths

Prefer commands that work regardless of whether you are running on macOS or inside a container.

**Option A (recommended): run from the skill directory**

This skill is typically installed/copied into a per-user skills folder at runtime, so
avoid repo-root assumptions like `skills/shared/...`.

Run from inside the skill folder:

```bash
uv run python scripts/deep_research.py --query "Research the history of Google TPUs"
```

**Option B: run from the parent skills directory (e.g., the user's skills dir)**

If your current directory is the skills folder that contains `gemini-deep-research/`:

```bash
uv run python gemini-deep-research/scripts/deep_research.py --query "Research the history of Google TPUs"
```

**Option C: use an explicit placeholder**

If you need to spell out an absolute path, use a placeholder like:

`<SKILL_DIR>/scripts/deep_research.py`

where `<SKILL_DIR>` is the runtime path to this skill folder (portable across macOS and containers).

### Examples

#### Basic Research

```bash
uv run python scripts/deep_research.py \
  --query "Research the history of Google TPUs"
```

#### Custom Output Format

```bash
uv run python scripts/deep_research.py \
  --query "Research the competitive landscape of EV batteries" \
  --format "1. Executive Summary\n2. Key Players (include data table)\n3. Supply Chain Risks"
```

#### With File Search (optional)

```bash
uv run python scripts/deep_research.py \
  --query "Compare our 2025 fiscal year report against current public web news" \
  --file-search-store "fileSearchStores/my-store-name"
```

#### Stream Progress

```bash
uv run python scripts/deep_research.py \
  --query "Your research topic" --stream
```

#### Custom Output Directory

```bash
uv run python scripts/deep_research.py \
  --query "Your research topic" \
  --output-dir <OUTPUT_DIR>
```

#### Override API Key

```bash
uv run python scripts/deep_research.py \
  --query "Your research topic" \
  --api-key "your-api-key"
```

## Output

The script saves results to timestamped files:
- `deep-research-YYYY-MM-DD-HH-MM-SS.md` - Final report in markdown
- `deep-research-YYYY-MM-DD-HH-MM-SS.json` - Full interaction metadata

## API Details

- **Endpoint**: `https://generativelanguage.googleapis.com/v1beta/interactions`
- **Agent**: `deep-research-pro-preview-12-2025`
- **Auth**: `x-goog-api-key` header (NOT OAuth Bearer token)

## Script Arguments

| Argument              | Required | Description                                 |
| --------------------- | -------- | ------------------------------------------- |
| `--query`             | Yes      | Research query/topic                        |
| `--format`            | No       | Custom output format instructions           |
| `--file-search-store` | No       | File search store name for document context |
| `--stream`            | No       | Show streaming progress updates             |
| `--output-dir`        | No       | Output directory for results (default: `.`) |
| `--api-key`           | No       | Override GEMINI_API_KEY env var             |

## Limitations

- Requires Gemini API key (get from [Google AI Studio](https://aistudio.google.com/apikey))
- Does NOT work with Antigravity OAuth authentication
- Long-running tasks (minutes to hours depending on complexity)
- May incur API costs depending on your quota

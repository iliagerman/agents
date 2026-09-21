---
name: tavily-search
description: AI-optimized web search via Tavily API. Returns concise, relevant results for AI agents.
version: 1.0.0
author: tavily
homepage: https://tavily.com
requires:
  bins:
    - node
  env:
    - name: TAVILY_API_KEY
      prompt: "Provide your Tavily API key (it will be stored in skills_secrets.yml and used for web search)."
      example: "tvly-..."
---

# Tavily Search

AI-optimized web search using Tavily API. Designed for AI agents - returns clean, relevant content.

## Runtime Rule

When this skill is loaded, the prompt should also include an **Attached Script Files** section with absolute runtime paths.

- Use the exact attached file path that ends with `/search.mjs` for search commands.
- Use the exact attached file path that ends with `/extract.mjs` for extraction commands.
- Do **not** invent alternate paths such as flat `/tmp/skills/...` paths.
- If the attached script files are missing, stop and report that the Tavily skill installation is incomplete.

## Search

First identify the attached absolute path for `search.mjs`, then run it with Node.

```bash
SEARCH_SCRIPT="/absolute/path/from-attached-script-files/search.mjs"
node "$SEARCH_SCRIPT" "query"
node "$SEARCH_SCRIPT" "query" -n 10
node "$SEARCH_SCRIPT" "query" --deep
node "$SEARCH_SCRIPT" "query" --topic news
```

### Options

- `-n <count>`: Number of results (default: 5, max: 20)
- `--deep`: Use advanced search for deeper research (slower, more comprehensive)
- `--topic <topic>`: Search topic - `general` (default) or `news`
- `--days <n>`: For news topic, limit to last n days

## Extract Content from URL

First identify the attached absolute path for `extract.mjs`, then run it with Node.

```bash
EXTRACT_SCRIPT="/absolute/path/from-attached-script-files/extract.mjs"
node "$EXTRACT_SCRIPT" "https://example.com/article"
node "$EXTRACT_SCRIPT" "url1" "url2" "url3"
```

Extracts raw content from one or more URLs for processing.

## Requirements

- `TAVILY_API_KEY` environment variable (get from https://tavily.com)
- Node.js runtime
- Attached runtime script files for `search.mjs` and `extract.mjs`

## Notes

- Tavily is optimized for AI - returns clean, relevant snippets
- Use `--deep` for complex research questions
- Use `--topic news` for current events
- The Node scripts read `TAVILY_API_KEY` directly from the environment, so you do not need to pass the API key as a command-line argument
- Prefer quoting the script path when running Node commands

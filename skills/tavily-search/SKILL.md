---
name: tavily_search
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

## Search

```bash
node ${MORDECAI_SKILLS_BASE_DIR}/[USER_NAME]/tavily-search/scripts/search.mjs "query"
node ${MORDECAI_SKILLS_BASE_DIR}/[USER_NAME]/tavily-search/scripts/search.mjs "query" -n 10
node ${MORDECAI_SKILLS_BASE_DIR}/[USER_NAME]/tavily-search/scripts/search.mjs "query" --deep
node ${MORDECAI_SKILLS_BASE_DIR}/[USER_NAME]/tavily-search/scripts/search.mjs "query" --topic news
```

### Options

- `-n <count>`: Number of results (default: 5, max: 20)
- `--deep`: Use advanced search for deeper research (slower, more comprehensive)
- `--topic <topic>`: Search topic - `general` (default) or `news`
- `--days <n>`: For news topic, limit to last n days

## Extract Content from URL

```bash
node ${MORDECAI_SKILLS_BASE_DIR}/[USER_NAME]/tavily-search/scripts/extract.mjs "https://example.com/article"
node ${MORDECAI_SKILLS_BASE_DIR}/[USER_NAME]/tavily-search/scripts/extract.mjs "url1" "url2" "url3"
```

Extracts raw content from one or more URLs for processing.

## Requirements

- `TAVILY_API_KEY` environment variable (get from https://tavily.com)
- Node.js runtime

## Notes

- Tavily is optimized for AI - returns clean, relevant snippets
- Use `--deep` for complex research questions
- Use `--topic news` for current events

#!/usr/bin/env python3
"""fuzzy.py — real fuzzy search over the brain (typo- and phrase-tolerant).

Walks every note via the storage layer (local or S3 — it doesn't care), scores
the query against each note's title, breadcrumb path, and body using rapidfuzz,
and returns the best matches with a snippet of the line that matched.

Requires: `pip install rapidfuzz`.
"""

from __future__ import annotations

import re

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - dependency guard
    import sys
    print("fuzzy: rapidfuzz is not installed. Run `pip install rapidfuzz`.",
          file=sys.stderr)
    raise

from storage import Storage

FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
H1_RE = re.compile(r"^#\s+(.*)$", re.MULTILINE)


def _title(rel: str, body: str) -> str:
    m = H1_RE.search(body)
    return m.group(1).strip() if m else rel.rsplit("/", 1)[-1][:-3]


def _breadcrumb(rel: str) -> str:
    # "personal/travel/summer-2026-ukraine/packing.md" -> "personal travel summer-2026-ukraine"
    parts = rel.split("/")[:-1]
    return " ".join(parts)


def _best_line(query: str, body: str) -> str:
    best, best_score = "", -1.0
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        score = fuzz.partial_ratio(query.lower(), line.lower())
        if score > best_score:
            best, best_score = line, score
    return best[:200]


def search(store: Storage, query: str, top: int = 5, threshold: float = 55.0) -> list[dict]:
    """Return up to `top` matches: {path, title, score, snippet}."""
    results: list[dict] = []
    for rel in store.walk_md():
        if rel.endswith("index.md"):
            continue  # indexes are navigation, not content
        try:
            raw = store.read_text(rel)
        except Exception:
            continue
        body = FRONTMATTER_RE.sub("", raw, count=1)
        title = _title(rel, body)
        crumb = _breadcrumb(rel)

        # Take the strongest signal across title, path, and body.
        score = max(
            fuzz.WRatio(query, title),
            fuzz.token_set_ratio(query, crumb),
            fuzz.partial_ratio(query.lower(), body.lower()),
        )
        if score < threshold:
            continue
        results.append({
            "path": rel,
            "title": title,
            "score": round(float(score), 1),
            "snippet": _best_line(query, body),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top]

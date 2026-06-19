# Structure & conventions

## The tree

```
$BRAIN_ROOT/
  index.md                         # single entry point; lists top-level clusters
  work/
    index.md
    <note>.md
  personal/
    index.md
    travel/
      index.md
      summer-2026-ukraine/
        index.md
        packing-list.md
  attachments/                     # all note attachments, mirroring the note tree
    personal/travel/summer-2026-ukraine/packing-list/
      tickets.pdf
      hotel.jpg
```

- **Cluster** = a directory + an `index.md`. A directory without an `index.md` is
  not a cluster (the tools ignore it for navigation).
- **Note** = any `*.md` in a cluster other than `index.md`.
- **Entry point** = the root `index.md`. Navigation always starts there and follows
  links down.
- **Attachments** = images/documents stored with a note. They live under a single
  `attachments/` folder at the brain root, mirroring the note's path
  (`attachments/<cluster>/<note-slug>/<file>`). That folder has no `index.md`, so it
  is invisible to `tree`/`check` navigation; the note body links to its files from an
  `## Attachments` section. Manage them with `add-note --attach`, `attach`,
  `get-attachments`, and `delete-note` — never by hand.

## `index.md` (the human-readable cluster map)

Created from `assets/cluster-index.md`. Shape:

```markdown
---
title: Travel
type: cluster
created: 2026-06-16
updated: 2026-06-16
---

# Travel

Parent: [up](../index.md)

Trips and destinations.            ← curated description of the cluster's subject/scope

## Sub-clusters
- [Summer 2026 Ukraine](summer-2026-ukraine/index.md) — Trip to Ukraine, summer 2026

## Notes
- [Travel insurance](travel-insurance.md) — Policy and emergency numbers
```

- The **description** paragraph and the one-line summaries after each link are
  **human-maintained** — keep them meaningful. `add-cluster`/`add-note` insert the
  links; you curate the words.
- Links are **relative to the cluster** (`summer-2026-ukraine/index.md`,
  `travel-insurance.md`); the breadcrumb is `../index.md`. The root index has no
  breadcrumb.
- `check` keeps the link lists honest against the real files; it never rewrites your
  prose.

## Notes

Created from `assets/note.md`:

```markdown
---
title: Packing list
type: note
created: 2026-06-16
updated: 2026-06-16
tags: [travel, checklist]
---

# Packing list

<body>
```

Keep notes focused and human-readable. The fuzzy search indexes the title,
breadcrumb path, and body — clear titles and headings improve recall.

## Paths & storage

- All tool arguments are **brain-relative** (`personal/travel/index.md`). The tools
  resolve them against `BRAIN_ROOT`.
- `BRAIN_ROOT` is either a local folder or an `s3://bucket/prefix` URI; the storage
  layer (`scripts/storage.py`) handles both behind the same interface, so the rest
  of the skill is backend-agnostic. For `s3://` roots, `boto3` must be installed and
  AWS credentials available; an optional `BRAIN_S3_ENDPOINT_URL` targets
  S3-compatible endpoints.

---
name: second-brain
description: "Manage a personal second brain — a tree of markdown notes grouped into nested subject clusters under a single entry point. Use when the user wants to capture, file, organize, find, or recall a note ('save this', 'add a note about X', 'where did I put…', 'what do my notes say about…', 'remember that…'). The brain lives at one path (local folder or s3:// URI) given by BRAIN_ROOT; the agent navigates the cluster tree to file notes in the right place, asks the user when placement is ambiguous, and fuzzy-searches to recall. Triggers on: second brain, my notes, save this note, file this, add a note, where did I put, recall, knowledge base, note cluster, organize my notes."
version: 1.0.0
requires:
  bins:
    - python3
  env:
    - name: BRAIN_ROOT
      required: false
      prompt: "Absolute path to the brain. Leave empty to use the default $HOME/second_brain. For the homeserver deployment, use /home/ilia/second_brain. S3 URIs are also supported (e.g. s3://my-bucket/brain)."
      example: "/home/ilia/second_brain"
---

# second-brain

A second brain is a **tree of subject clusters** with a single entry point
(`index.md` at the root). Clusters nest as deep as the subject needs:

```
$BRAIN_ROOT/index.md            ← the one entry point
  personal/index.md
    travel/index.md
      summer-2026-ukraine/index.md
        packing-list.md         ← notes live in clusters
  work/index.md
```

- A **cluster** = a folder + an `index.md` that describes its subject and links its
  sub-clusters and notes (human-readable; you maintain it).
- A **note** = a markdown file inside a cluster.
- Everything is plain markdown under **one path**, `BRAIN_ROOT`. If `BRAIN_ROOT`
  is unset or empty, the scripts default it to `$HOME/second_brain` and create the
  folder if needed. If the value is an `s3://…` URI the scripts use S3 internally;
  otherwise it's a local folder. You never write S3-specific code, and
  mounting/syncing that path is a deployment concern, not the skill's.

Full conventions: `references/structure.md`. The placement decision rules:
`references/placement.md`. The complete per-command contract: `references/commands.md`.

## The tools (all via `python3 scripts/brain.py …`, paths are brain-relative)

| Command | Use it to… | Run it… |
|---|---|---|
| `init` | create the root `index.md` | once, on an empty brain |
| `tree` | see the whole hierarchy | at the **start** of any filing/organizing task |
| `show <path>` | read a cluster index or note | to inspect a cluster's scope before placing |
| `search <q> [--top N]` | fuzzy-find notes (typo/phrase tolerant) | to **recall**, and **before adding** (dedupe + find home) |
| `add-cluster --parent P --name SLUG --title T --desc D` | create a cluster + link it in its parent | **only** when placement says "new cluster" |
| `add-note --cluster C --title T [--summary S] [--tags a,b] [--attach FILE …]` (body on stdin) | create a note + link it in the cluster (and store any attached images/docs) | after the target cluster is decided |
| `attach --note <path> --file FILE [--file FILE …]` | add images/documents to an **existing** note | when the user adds files to a note they already have |
| `get-attachments <path> [--out DIR]` | copy a note's attachments out to a directory (default cwd) | to **retrieve/show** a note's images/docs back to the user |
| `delete-note <path>` | delete a note, its attachments, and its index link | when the user asks to remove/delete a note |
| `check [path]` | report `index.md` drift vs real files | **after every change**, until clean |

> **Attachments** (images, PDFs, any document) live under a single `attachments/`
> folder at the brain root, mirroring each note's path
> (`attachments/<cluster>/<note-slug>/<file>`). The note body gets an `## Attachments`
> section with an inline `![](…)` embed for images and a `[](…)` link for other
> files. Use `--attach`/`attach` to add them, `get-attachments` to hand them back,
> and `delete-note` removes a note's attachment folder automatically. Attachment
> source paths are ordinary filesystem paths (e.g. a file the user just uploaded).

> **Hard rule:** never create/edit files under `BRAIN_ROOT` with raw Write/Edit
> when a `brain.py` command exists — the commands keep `index.md` links correct.
> Use Edit only to refine the *human-readable prose* (a cluster description, a note
> body, a one-line summary) in a file a command already created, then run `check`.

## Filing a new note — the workflow

1. **Orient:** `tree`, then read the root `index.md`.
2. **Recall/dedupe:** `search "<topic>"` — does a similar note/cluster already exist?
3. **Locate** the most specific cluster whose subject fits (descend, `show`ing
   candidate indexes).
4. **Decide** (rules in `references/placement.md`):
   - **Existing cluster** if one clearly fits and no finer grouping is warranted.
   - **New sub-cluster** if the note opens a distinct sub-subject likely to gather
     more notes (a new trip, a new project), or an existing cluster needs splitting.
   - **New top-level cluster** only if no top-level subject fits.
   - **Don't over-nest:** a one-off note goes in the nearest fitting cluster — never
     a speculative single-note cluster.
5. **Ask when ambiguous** — if two clusters fit comparably, or it's unclear whether
   to reuse vs create a cluster, ask the user a short question naming the candidate
   locations plus a "new cluster" option. Example: *"Is this about your Ukraine trip
   (Personal → Travel → Summer 2026 Ukraine), work travel, or a new subject?"*
   Proceed only after they pick.
6. **Write:** `add-cluster` (only if creating one), then `add-note`. If the user
   supplied images or documents with the note, pass each one as `--attach FILE`
   (repeat per file) so they are stored with the note. To add files to a note
   that already exists, use `attach --note <path> --file FILE`.
7. **Re-evaluate indexes (mandatory):** run `check` from the touched path up to the
   root; fix every reported index (keep prose human-readable); re-run until clean.
8. **Confirm** the final breadcrumb path to the user.

## Recall — the workflow

`search "<question>"` → `show` the top hits → answer **citing** the notes by path.
If nothing relevant comes back, say so — it's a gap to fill, not a reason to guess.
If a recalled note has an `## Attachments` section and the user wants the files
back (not just the text), run `get-attachments <note-path>` to copy them out for
delivery.

## Deleting a note — the workflow

`search "<description of note>"` → `show` the matching note to confirm → `delete-note <path>` → `check` from the affected cluster up to root until clean → confirm the deleted path. `delete-note` also removes the note's `attachments/` sub-folder, so any stored images/documents go with it.

## Setup

```bash
export BRAIN_ROOT="$HOME/second_brain"      # optional; this is the default. Homeserver: /home/ilia/second_brain
pip install -r requirements.txt              # rapidfuzz (search) + boto3 (only for s3://)
python3 scripts/brain.py init                # once
```

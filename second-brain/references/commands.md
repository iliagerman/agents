# Command operating contract

The authoritative "how and when" for every `brain.py` command. SKILL.md has the
quick table; this is the detail the agent must follow exactly.

All `<path>` arguments are **brain-relative POSIX** paths (`personal/travel/index.md`),
never absolute and never including `BRAIN_ROOT`. The empty string (or omitting
`--parent`/`--cluster`) means the root.

> **Hard rule — never bypass the CLI for structural writes.** Do not create or
> rename files/folders under `BRAIN_ROOT`, and do not hand-edit the link lists in
> `index.md`, with raw Write/Edit tools. `add-cluster`/`add-note` insert the links
> deterministically; bypassing them causes drift. Edit is allowed **only** to
> improve human-readable prose (a cluster `description`, a note body, a one-line
> summary) inside a file a command already created — and you must run `check`
> afterward.

How writes split between tool and agent:
- The **command** does the mechanical part: create the file from a template and
  insert the link into the parent/cluster `index.md`.
- The **agent** then curates the human-readable parts (cluster description, note
  summaries, note body) and runs `check`.

---

## `init [--title T]`
- **Purpose:** create the root `index.md` (the single entry point).
- **When:** once, on a brand-new/empty brain. Safe to re-run (no-op if it exists).
- **Then:** start adding top-level clusters with `add-cluster` (no `--parent`).

## `tree`
- **Purpose:** print the entire cluster/note hierarchy.
- **When:** at the **start of every filing or organizing task**, and any time you
  need the current shape before deciding placement.
- **Skip:** pure recall tasks (use `search`).
- **Then:** `show` the candidate cluster indexes you're considering.

## `show <path>`
- **Purpose:** print a cluster `index.md` or a note.
- **When:** to read a candidate cluster's **description/scope** before placing a
  note there; to read a note before refining it.
- **Example:** `show personal/travel/index.md`.

## `search <query> [--top N]`
- **Purpose:** fuzzy-find notes by word or phrase (typo-tolerant; ignores index
  files — it searches note *content*).
- **When:**
  1. **Recall** — answering "what do my notes say about X / where did I put Y".
  2. **Before adding any note** — confirm a similar note/cluster doesn't already
     exist (dedupe) and discover the right home.
  3. When the user refers to something vaguely.
- **Read-only — safe anytime.** **Then:** `show` the hits to read them in full.

## `add-cluster --parent P --name SLUG --title T --desc D`
- **Purpose:** create a new cluster (folder + `index.md` from template) and link it
  into the parent index.
- **When — only after the placement rules conclude "new cluster":** a distinct
  sub-subject likely to accumulate more notes, a needed split of a heterogeneous
  cluster, or a new top-level subject with no existing fit.
- **Do NOT:** create a cluster for a single one-off note (over-nesting); create one
  when a fitting cluster already exists.
- **Preconditions:** you ran `tree` + `search`; if placement was ambiguous you
  **asked the user** and they chose.
- **Args:** `--parent` blank = top level; `--name` is the folder slug (kebab-case);
  `--title` is the human title; `--desc` is the one-line subject/scope.
- **Then:** usually `add-note` into it immediately; refine `--desc` for clarity;
  run `check`.

## `add-note --cluster C --title T [--summary S] [--tags a,b] [--attach FILE …]`  (body on **stdin**)
- **Purpose:** create a note in a cluster and link it in that cluster's `index.md`.
- **When:** after the target cluster is decided (existing or just created).
- **Preconditions:** the target cluster exists; placement confirmed (or asked).
- **Body:** piped on stdin, e.g. `echo "..." | brain.py add-note --cluster … --title …`
  or a heredoc. `--summary` becomes the one-line description shown in the index.
- **Attachments:** pass `--attach FILE` once per file (image, PDF, any document) the
  user supplied with the note. Each file is copied under the brain-root
  `attachments/<cluster>/<note-slug>/` folder and referenced from an
  `## Attachments` section in the note body (inline `![]` for images, `[]` links
  otherwise). If any `--attach` path doesn't exist the note is **not** created.
- **Then:** `check` from the cluster up to root; curate the note body and its index
  summary for readability; confirm the breadcrumb path to the user.

## `attach --note <path> --file FILE [--file FILE …]`
- **Purpose:** add one or more images/documents to a note that already exists.
- **When:** the user wants to add files to an existing note (rather than at creation).
- **Preconditions:** the note exists (run `search`/`show` to find it); the source
  files exist on disk.
- **Args:** `--note` is the brain-relative note path; `--file` is repeatable.
- **Effect:** copies the files under `attachments/<cluster>/<note-slug>/`, de-duplicates
  names, and appends them to the note's `## Attachments` section.
- **Then:** `check` (attachments don't affect index links, but stay in the habit).

## `get-attachments <path> [--out DIR]`
- **Purpose:** copy a note's stored attachments out to a directory so they can be
  handed back to the user (e.g. delivered as files).
- **When:** recalling/reviewing a note and the user wants the actual images/documents,
  not just the note text.
- **Args:** `path` is the brain-relative note path; `--out` is the destination dir
  (defaults to the current working directory). Prints each copied file path.
- **Read-only on the brain** — it never modifies notes.

## `delete-note <path>`
- **Purpose:** delete a note, its attachments, and its link in the cluster index.
- **When:** when the user asks to delete/remove a note from the second brain.
- **Preconditions:** run `search` and usually `show` first so you delete the intended note.
- **Args:** `path` is brain-relative, e.g. `travel/poland-slovakia-2026/car-rental-booking.md`.
- **Effect:** removes the note file, removes its `attachments/<cluster>/<note-slug>/`
  folder (and everything in it), and strips its link from the cluster index.
- **Then:** run `check` from the affected cluster up to root until clean and confirm the deleted path.

## `check [path]`
- **Purpose:** report drift between `index.md` files and the real files — notes or
  sub-clusters not linked, and stale links pointing at files that don't exist.
- **When — mandatory after every change** (`add-note`, `add-cluster`, any manual
  prose edit, or files synced in from another machine). Optionally scope it to a
  subtree (`check personal/travel`).
- **Then:** fix each reported index (add the missing link, remove the stale one —
  keeping prose human-readable) and **re-run until it prints `✓`**. Exit code is
  non-zero while drift remains, zero when clean.

---

## Standard sequences

- **File a note (with files):** `tree` → `search "<topic>"` → decide →
  *(ask if ambiguous)* → `add-cluster` *(only if new)* →
  `add-note … --attach FILE` *(one per supplied file)* → curate → `check` → fix →
  `check` until `✓` → confirm path.
- **Add files to an existing note:** `search`/`show` to locate →
  `attach --note <path> --file FILE …` → confirm.
- **Recall (with files):** `search "<question>"` → `show` top hits → cited answer;
  if the user wants the files, `get-attachments <path>` → deliver them.
- **Delete a note:** `search "<description>"` → `show` likely match → `delete-note <path>`
  (removes its attachments too) → `check` until `✓` → confirm deletion.
- **Audit/reorganize:** `tree` → `check` → repair indexes → `check` until `✓`.

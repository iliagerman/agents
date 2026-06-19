#!/usr/bin/env python3
"""brain.py — the second brain CLI. Works identically on a local folder or an
S3 path (decided by the shape of BRAIN_ROOT; see storage.py).

Commands:
  tree                                   show the whole cluster/note hierarchy
  show <path>                            print an index or note
  search <query> [--top N]               fuzzy search note contents
  add-cluster --parent P --name SLUG --title T --desc D
  add-note --cluster C --title T [--summary S] [--tags a,b]   (body on stdin)
  check [path]                           report index.md drift vs the real files

All <path> arguments are brain-relative (e.g. personal/travel/index.md).
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
from datetime import date
from pathlib import Path

from storage import Listing, Storage, brain_root, get_storage

LINK_RE = re.compile(r"\]\(([^)]+)\)")

# Image extensions get an inline ![] embed in the note; everything else a [] link.
IMAGE_EXTS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff"}
)

# All note attachments live under a single folder at the brain root; inside it
# they mirror the note's path so each note owns an isolated, collision-free
# sub-folder (e.g. attachments/travel/poland-2026/hotel.jpg for travel/poland-2026.md).
ATTACHMENTS_ROOT = "attachments"


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "untitled"


def _today() -> str:
    return date.today().isoformat()


def _read_template(name: str) -> str:
    from pathlib import Path
    return (Path(__file__).resolve().parent.parent / "assets" / name).read_text("utf-8")


# --------------------------------------------------------------------------- #
# tree / show
# --------------------------------------------------------------------------- #
def _tree(store: Storage, rel: str, prefix: str, lines: list[str]) -> None:
    listing = store.list_dir(rel)
    entries = [("cluster", c) for c in listing.clusters] + \
              [("note", n) for n in listing.notes]
    for i, (kind, name) in enumerate(entries):
        last = i == len(entries) - 1
        branch = "└── " if last else "├── "
        if kind == "cluster":
            lines.append(f"{prefix}{branch}{name}/")
            child_prefix = prefix + ("    " if last else "│   ")
            _tree(store, store._join(rel, name), child_prefix, lines)
        else:
            lines.append(f"{prefix}{branch}{name}")


def cmd_tree(store: Storage, args) -> int:
    root_label = brain_root().rstrip("/").rsplit("/", 1)[-1] or "brain"
    lines = [f"{root_label}/"]
    _tree(store, "", "", lines)
    print("\n".join(lines))
    return 0


def cmd_init(store: Storage, args) -> int:
    if store.exists("index.md"):
        print("already initialized (root index.md exists)")
        return 0
    tmpl = _read_template("cluster-index.md")
    content = (tmpl
               .replace("__TITLE__", args.title)
               .replace("__DESC__", "Single entry point. Top-level clusters group "
                        "everything by subject; descend to find notes.")
               .replace("__BREADCRUMB__", "index.md")  # root points at itself
               .replace("__DATE__", _today()))
    # Root has no parent — drop the breadcrumb line.
    content = content.replace("Parent: [up](index.md)\n\n", "")
    store.write_text("index.md", content)
    print(f"initialized brain at {brain_root()} (root index.md created)")
    return 0


def cmd_show(store: Storage, args) -> int:
    if not store.exists(args.path):
        print(f"not found: {args.path}", file=sys.stderr)
        return 1
    print(store.read_text(args.path))
    return 0


# --------------------------------------------------------------------------- #
# search
# --------------------------------------------------------------------------- #
def cmd_search(store: Storage, args) -> int:
    import fuzzy  # lazy: only `search` needs rapidfuzz
    hits = fuzzy.search(store, args.query, top=args.top)
    if not hits:
        print(f"no matches for {args.query!r}")
        return 0
    for h in hits:
        print(f"[{h['score']:>5}] {h['path']}")
        print(f"        {h['title']}")
        if h["snippet"]:
            print(f"        … {h['snippet']}")
    return 0


# --------------------------------------------------------------------------- #
# index helpers — append a link under a "## Sub-clusters" / "## Notes" heading
# --------------------------------------------------------------------------- #
def _append_under_heading(text: str, heading: str, line: str) -> str:
    """Insert `line` as the last bullet under `## heading`, creating the section
    if absent. Idempotent: skips if the exact line is already present."""
    if line in text:
        return text
    lines = text.splitlines()
    h = f"## {heading}"
    if h in lines:
        idx = lines.index(h) + 1
        # advance past existing bullets/blank lines to the end of the section
        end = idx
        while end < len(lines) and not lines[end].startswith("## "):
            end += 1
        # trim trailing blanks inside the section, then insert
        insert_at = end
        while insert_at > idx and not lines[insert_at - 1].strip():
            insert_at -= 1
        lines.insert(insert_at, line)
        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    # section missing — append it
    sep = "" if text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return f"{text}{sep}## {heading}\n\n{line}\n"


def _link_targets(text: str) -> set[str]:
    return {m.group(1).split("#")[0] for m in LINK_RE.finditer(text)}


def _remove_link_to_target(text: str, target: str) -> str:
    """Remove markdown bullet lines that link to target."""
    kept: list[str] = []
    for line in text.splitlines():
        targets = _link_targets(line)
        if line.lstrip().startswith("-") and target in targets:
            continue
        kept.append(line)
    return "\n".join(kept) + ("\n" if text.endswith("\n") else "")


# --------------------------------------------------------------------------- #
# attachments — files (images/docs) stored beside a note in <slug>.attachments/
# --------------------------------------------------------------------------- #
def _normalize_note_path(raw: str) -> str:
    """Turn a user-supplied note path into a brain-relative `<…>.md` path."""
    note_rel = raw.strip("/")
    if not note_rel or note_rel.endswith("/") or note_rel.endswith("index.md"):
        return ""
    if not note_rel.endswith(".md"):
        note_rel = f"{note_rel}.md"
    return note_rel


def _attachments_dir(note_rel: str) -> str:
    """The note's attachment folder under the brain-root attachments tree.

    Mirrors the note path: `travel/poland-2026.md` -> `attachments/travel/poland-2026`.
    """
    stem = note_rel[:-3] if note_rel.endswith(".md") else note_rel
    return f"{ATTACHMENTS_ROOT}/{stem}"


def _attachment_bullet(link: str, name: str) -> str:
    """Render an attachment as an inline image embed or a plain link bullet."""
    if Path(name).suffix.lower() in IMAGE_EXTS:
        return f"- ![{name}]({link})"
    return f"- [{name}]({link})"


def _copy_attachments(store: Storage, note_rel: str, sources: list[str]) -> list[str]:
    """Copy each source file into the note's attachments dir.

    Validates every source up front (all-or-nothing), de-duplicates names within
    the folder, and returns the markdown bullet lines to add to the note body.
    Links are relative to the note's own location so they resolve in any viewer.
    """
    resolved: list[Path] = []
    for src in sources:
        p = Path(src).expanduser()
        if not p.is_file():
            print(f"attachment not found: {src}", file=sys.stderr)
            return []
        resolved.append(p)

    adir = _attachments_dir(note_rel)
    note_dir = note_rel.rpartition("/")[0]
    bullets: list[str] = []
    for p in resolved:
        name = _dedupe_attachment_name(store, adir, Path(p.name).name)
        att_rel = store._join(adir, name)
        store.write_bytes(att_rel, p.read_bytes())
        link = posixpath.relpath(att_rel, note_dir) if note_dir else att_rel
        bullets.append(_attachment_bullet(link, name))
    return bullets


def _dedupe_attachment_name(store: Storage, adir: str, name: str) -> str:
    """Return a name that does not collide with an existing attachment."""
    if not store.exists(store._join(adir, name)):
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 1
    while True:
        candidate = f"{stem}-{counter}{suffix}"
        if not store.exists(store._join(adir, candidate)):
            return candidate
        counter += 1


def _append_attachment_bullets(store: Storage, note_rel: str, bullets: list[str]) -> None:
    """Add attachment bullets under the note's `## Attachments` heading."""
    text = store.read_text(note_rel)
    for bullet in bullets:
        text = _append_under_heading(text, "Attachments", bullet)
    store.write_text(note_rel, text)


# --------------------------------------------------------------------------- #
# add-cluster / add-note / delete-note
# --------------------------------------------------------------------------- #
def cmd_add_cluster(store: Storage, args) -> int:
    parent = args.parent.strip("/").removesuffix("/index.md")
    if parent and not store.is_cluster(parent):
        print(f"parent cluster not found: {parent or '(root)'}", file=sys.stderr)
        return 1
    cluster_rel = store._join(parent, args.name)
    index_rel = store._join(cluster_rel, "index.md")
    if store.exists(index_rel):
        print(f"cluster already exists: {cluster_rel}", file=sys.stderr)
        return 1

    breadcrumb = "../index.md" if parent else "../index.md"
    tmpl = _read_template("cluster-index.md")
    content = (tmpl
               .replace("__TITLE__", args.title)
               .replace("__DESC__", args.desc)
               .replace("__BREADCRUMB__", breadcrumb)
               .replace("__DATE__", _today()))
    store.write_text(index_rel, content)

    # Link the new cluster into the parent index.
    parent_index = store._join(parent, "index.md")
    if store.exists(parent_index):
        ptext = store.read_text(parent_index)
        link = f"- [{args.title}]({args.name}/index.md) — {args.desc}"
        store.write_text(parent_index, _append_under_heading(ptext, "Sub-clusters", link))

    print(f"created cluster {cluster_rel}")
    return 0


def cmd_add_note(store: Storage, args) -> int:
    cluster = args.cluster.strip("/").removesuffix("/index.md")
    if cluster and not store.is_cluster(cluster):
        print(f"cluster not found: {cluster or '(root)'}", file=sys.stderr)
        return 1
    slug = _slug(args.title)
    note_rel = store._join(cluster, f"{slug}.md")
    if store.exists(note_rel):
        print(f"note already exists: {note_rel}", file=sys.stderr)
        return 1

    # Validate attachment sources before creating the note so a bad path never
    # leaves an orphaned note behind.
    missing = [s for s in (args.attach or []) if not Path(s).expanduser().is_file()]
    if missing:
        for src in missing:
            print(f"attachment not found: {src}", file=sys.stderr)
        return 1

    body = sys.stdin.read() if not sys.stdin.isatty() else ""
    tags = ", ".join(t.strip() for t in (args.tags or "").split(",") if t.strip())
    tags_yaml = f"[{tags}]" if tags else "[]"
    tmpl = _read_template("note.md")
    content = (tmpl
               .replace("__TITLE__", args.title)
               .replace("__DATE__", _today())
               .replace("__TAGS_YAML__", tags_yaml)
               .replace("__BODY__", body.strip()))
    store.write_text(note_rel, content)

    index_rel = store._join(cluster, "index.md")
    if store.exists(index_rel):
        itext = store.read_text(index_rel)
        suffix = f" — {args.summary}" if args.summary else ""
        link = f"- [{args.title}]({slug}.md){suffix}"
        store.write_text(index_rel, _append_under_heading(itext, "Notes", link))

    attachments = args.attach or []
    if attachments:
        bullets = _copy_attachments(store, note_rel, attachments)
        if not bullets:
            return 1
        _append_attachment_bullets(store, note_rel, bullets)

    print(f"created note {note_rel}" + (f" (+{len(attachments)} attachment(s))" if attachments else ""))
    return 0


def cmd_attach(store: Storage, args) -> int:
    note_rel = _normalize_note_path(args.note)
    if not note_rel:
        print("attach requires a brain-relative note path, not a cluster index", file=sys.stderr)
        return 1
    if not store.exists(note_rel):
        print(f"note not found: {note_rel}", file=sys.stderr)
        return 1

    bullets = _copy_attachments(store, note_rel, args.file)
    if not bullets:
        return 1
    _append_attachment_bullets(store, note_rel, bullets)
    print(f"attached {len(bullets)} file(s) to {note_rel}")
    return 0


def cmd_get_attachments(store: Storage, args) -> int:
    note_rel = _normalize_note_path(args.path)
    if not note_rel:
        print("get-attachments requires a brain-relative note path", file=sys.stderr)
        return 1
    if not store.exists(note_rel):
        print(f"note not found: {note_rel}", file=sys.stderr)
        return 1

    adir = _attachments_dir(note_rel)
    names = store.list_files(adir)
    if not names:
        print(f"no attachments for {note_rel}")
        return 0

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (out_dir / name).write_bytes(store.read_bytes(store._join(adir, name)))
        print(str((out_dir / name).resolve()))
    return 0


def cmd_delete_note(store: Storage, args) -> int:
    note_rel = _normalize_note_path(args.path)
    if not note_rel:
        print(
            "delete-note requires a brain-relative note path, not a cluster index",
            file=sys.stderr,
        )
        return 1
    if not store.exists(note_rel):
        print(f"note not found: {note_rel}", file=sys.stderr)
        return 1

    parent, _, filename = note_rel.rpartition("/")
    index_rel = store._join(parent, "index.md")
    if store.exists(index_rel):
        index_text = store.read_text(index_rel)
        store.write_text(index_rel, _remove_link_to_target(index_text, filename))

    store.delete(note_rel)
    store.delete_prefix(_attachments_dir(note_rel))
    print(f"deleted note {note_rel}")
    return 0


# --------------------------------------------------------------------------- #
# check — drift between index.md and the real files
# --------------------------------------------------------------------------- #
def _check_cluster(store: Storage, rel: str, problems: list[str]) -> None:
    index_rel = store._join(rel, "index.md")
    listing: Listing = store.list_dir(rel)
    expected = {f"{n}" for n in listing.notes} | {f"{c}/index.md" for c in listing.clusters}
    referenced = _link_targets(store.read_text(index_rel)) if store.exists(index_rel) else set()

    label = rel or "(root)"
    if not store.exists(index_rel):
        problems.append(f"{label}: missing index.md")
    for missing in sorted(expected - referenced):
        problems.append(f"{label}: not linked in index.md -> {missing}")
    # stale: a local .md link with no matching file (ignore breadcrumb + externals)
    for ref in sorted(referenced):
        if ref in ("../index.md", "index.md") or "://" in ref:
            continue
        if ref.endswith(".md") and ref not in expected and not store.exists(store._join(rel, ref)):
            problems.append(f"{label}: stale link in index.md -> {ref}")

    for c in listing.clusters:
        _check_cluster(store, store._join(rel, c), problems)


def cmd_check(store: Storage, args) -> int:
    problems: list[str] = []
    _check_cluster(store, args.path.strip("/"), problems)
    if not problems:
        print("✓ indexes are in sync with the files")
        return 0
    print(f"✗ {len(problems)} drift issue(s):")
    for p in problems:
        print(f"  - {p}")
    return 1


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="Second brain CLI.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create the root index.md (run once)")
    p_init.add_argument("--title", default="Second Brain")

    sub.add_parser("tree", help="show the cluster/note hierarchy")

    p_show = sub.add_parser("show", help="print an index or note")
    p_show.add_argument("path")

    p_search = sub.add_parser("search", help="fuzzy search note contents")
    p_search.add_argument("query")
    p_search.add_argument("--top", type=int, default=5)

    p_ac = sub.add_parser("add-cluster", help="create a cluster + link it in parent")
    p_ac.add_argument("--parent", default="", help="parent cluster (blank = root)")
    p_ac.add_argument("--name", required=True, help="directory slug")
    p_ac.add_argument("--title", required=True)
    p_ac.add_argument("--desc", required=True, help="one-line subject/scope")

    p_an = sub.add_parser("add-note", help="create a note + link it in the cluster")
    p_an.add_argument("--cluster", default="", help="target cluster (blank = root)")
    p_an.add_argument("--title", required=True)
    p_an.add_argument("--summary", default="", help="one-line summary for the index")
    p_an.add_argument("--tags", default="", help="comma-separated")
    p_an.add_argument(
        "--attach", action="append", metavar="FILE",
        help="path to a file (image/doc) to store with the note; repeatable",
    )

    p_at = sub.add_parser("attach", help="add attachments to an existing note")
    p_at.add_argument("--note", required=True, help="brain-relative note path")
    p_at.add_argument(
        "--file", action="append", required=True, metavar="FILE",
        help="path to a file (image/doc) to attach; repeatable",
    )

    p_ga = sub.add_parser(
        "get-attachments", help="copy a note's attachments out to a directory"
    )
    p_ga.add_argument("path", help="brain-relative note path")
    p_ga.add_argument("--out", default=".", help="destination directory (default: cwd)")

    p_dn = sub.add_parser("delete-note", help="delete a note + remove its index link")
    p_dn.add_argument("path", help="brain-relative note path")

    p_chk = sub.add_parser("check", help="report index.md drift")
    p_chk.add_argument("path", nargs="?", default="", help="subtree to check (default: root)")

    args = parser.parse_args()
    store = get_storage()
    dispatch = {
        "init": cmd_init,
        "tree": cmd_tree, "show": cmd_show, "search": cmd_search,
        "add-cluster": cmd_add_cluster, "add-note": cmd_add_note,
        "attach": cmd_attach, "get-attachments": cmd_get_attachments,
        "delete-note": cmd_delete_note, "check": cmd_check,
    }
    return dispatch[args.cmd](store, args)


if __name__ == "__main__":
    sys.exit(main())

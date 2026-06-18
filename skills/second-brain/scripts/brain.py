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
import re
import sys
from datetime import date

from storage import Listing, Storage, brain_root, get_storage

LINK_RE = re.compile(r"\]\(([^)]+)\)")


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "untitled"


def _today() -> str:
    return date.today().isoformat()


def _read_template(name: str) -> str:
    from pathlib import Path
    return (Path(__file__).resolve().parent.parent / "templates" / name).read_text("utf-8")


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
               .replace("{{TITLE}}", args.title)
               .replace("{{DESC}}", "Single entry point. Top-level clusters group "
                        "everything by subject; descend to find notes.")
               .replace("{{BREADCRUMB}}", "index.md")  # root points at itself
               .replace("{{DATE}}", _today()))
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


# --------------------------------------------------------------------------- #
# add-cluster / add-note
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
               .replace("{{TITLE}}", args.title)
               .replace("{{DESC}}", args.desc)
               .replace("{{BREADCRUMB}}", breadcrumb)
               .replace("{{DATE}}", _today()))
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

    body = sys.stdin.read() if not sys.stdin.isatty() else ""
    tags = ", ".join(t.strip() for t in (args.tags or "").split(",") if t.strip())
    tmpl = _read_template("note.md")
    content = (tmpl
               .replace("{{TITLE}}", args.title)
               .replace("{{DATE}}", _today())
               .replace("{{TAGS}}", tags)
               .replace("{{BODY}}", body.strip()))
    store.write_text(note_rel, content)

    index_rel = store._join(cluster, "index.md")
    if store.exists(index_rel):
        itext = store.read_text(index_rel)
        suffix = f" — {args.summary}" if args.summary else ""
        link = f"- [{args.title}]({slug}.md){suffix}"
        store.write_text(index_rel, _append_under_heading(itext, "Notes", link))

    print(f"created note {note_rel}")
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

    p_chk = sub.add_parser("check", help="report index.md drift")
    p_chk.add_argument("path", nargs="?", default="", help="subtree to check (default: root)")

    args = parser.parse_args()
    store = get_storage()
    dispatch = {
        "init": cmd_init,
        "tree": cmd_tree, "show": cmd_show, "search": cmd_search,
        "add-cluster": cmd_add_cluster, "add-note": cmd_add_note, "check": cmd_check,
    }
    return dispatch[args.cmd](store, args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Install, update, or migrate AWS AI-DLC Workflows 2.x in a project."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

V2_ZIP = "https://github.com/awslabs/aidlc-workflows/archive/refs/heads/v2.zip"
AGENT_DIRS = {
    "claude": [".claude"],
    "codex": [".codex", ".agents"],
    "kiro": [".kiro"],
    "kiro-ide": [".kiro"],
    "opencode": [".aidlc", ".opencode"],
    "copilot": [".aidlc", ".github"],
}
AGENTS_MARKER_START = "<!-- BEGIN AWS AI-DLC v2 -->"
AGENTS_MARKER_END = "<!-- END AWS AI-DLC v2 -->"
GITIGNORE_MARKER_START = "# BEGIN AWS AI-DLC v2"
GITIGNORE_MARKER_END = "# END AWS AI-DLC v2"


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "aidlc-skill-v2"})
    with urllib.request.urlopen(request) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def extract_source(temp_dir: Path) -> Path:
    archive = temp_dir / "aidlc-v2.zip"
    download(V2_ZIP, archive)
    extracted = temp_dir / "source"
    with zipfile.ZipFile(archive) as zip_file:
        zip_file.extractall(extracted)
    candidates = [path.parent.parent for path in extracted.rglob("dist/claude")]
    if len(candidates) != 1:
        raise SystemExit("Downloaded v2 archive has no unique dist/claude tree")
    return candidates[0]


def framework_version(source: Path) -> str:
    version_file = source / "core" / "tools" / "aidlc-version.ts"
    match = re.search(r'AIDLC_VERSION\s*=\s*"([^"]+)"', version_file.read_text())
    if not match:
        raise SystemExit("Cannot read AI-DLC version from v2 source")
    return match.group(1)


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot merge {path}: {error}") from error


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def copy_missing_tree(source: Path, target: Path) -> None:
    for source_path in source.rglob("*"):
        relative = source_path.relative_to(source)
        target_path = target / relative
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
        elif not target_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)


def contains_aidlc_hook(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_aidlc_hook(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_aidlc_hook(item) for item in value)
    return isinstance(value, str) and "/hooks/aidlc-" in value


def merge_claude_settings(existing: dict[str, Any], shipped: dict[str, Any]) -> dict[str, Any]:
    """Merge AI-DLC mechanics without changing the user's Claude runtime."""
    announcements = [item for item in existing.get("companyAnnouncements", []) if "# AI-DLC" not in item]
    existing["companyAnnouncements"] = announcements + shipped.get("companyAnnouncements", [])
    permissions = existing.setdefault("permissions", {})
    allowed = permissions.setdefault("allow", [])
    allowed.extend(item for item in shipped.get("permissions", {}).get("allow", []) if item not in allowed)
    if "statusLine" in shipped:
        existing.setdefault("statusLine", shipped["statusLine"])
    hooks = existing.setdefault("hooks", {})
    for event, registrations in shipped.get("hooks", {}).items():
        current = [item for item in hooks.get(event, []) if not contains_aidlc_hook(item)]
        hooks[event] = current + registrations
    return existing


def deep_defaults(existing: dict[str, Any], shipped: dict[str, Any]) -> dict[str, Any]:
    for key, value in shipped.items():
        if key not in existing:
            existing[key] = value
        elif isinstance(value, dict) and isinstance(existing[key], dict):
            deep_defaults(existing[key], value)
    return existing


def merge_opencode_config(project: Path, distribution: Path) -> None:
    target = project / "opencode.json"
    shipped = read_json(distribution / "opencode.json")
    if not target.exists():
        write_json(target, shipped)
        return
    existing = read_json(target)
    existing.setdefault("$schema", shipped["$schema"])
    paths = existing.setdefault("skills", {}).setdefault("paths", [])
    paths.extend(item for item in shipped["skills"]["paths"] if item not in paths)
    instructions = existing.setdefault("instructions", [])
    instructions.extend(item for item in shipped["instructions"] if item not in instructions)
    for group, rules in shipped["permission"].items():
        target_rules = existing.setdefault("permission", {}).setdefault(group, {})
        for pattern, action in rules.items():
            if pattern != "*":
                target_rules[pattern] = action
    write_json(target, existing)


def replace_marked_block(path: Path, start: str, end: str, content: str) -> None:
    block = f"{start}\n{content.rstrip()}\n{end}"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    updated = pattern.sub(block, existing) if pattern.search(existing) else f"{existing.rstrip()}\n\n{block}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated.lstrip() if not existing else updated, encoding="utf-8")


def merge_agents(project: Path, distribution: Path) -> None:
    source = distribution / "AGENTS.md"
    if source.exists():
        replace_marked_block(
            project / "AGENTS.md",
            AGENTS_MARKER_START,
            AGENTS_MARKER_END,
            source.read_text(encoding="utf-8"),
        )


def merge_gitignore(project: Path, distribution: Path) -> None:
    source = distribution / ".gitignore"
    text = source.read_text(encoding="utf-8")
    marker = text.find("# AI-DLC")
    if marker < 0:
        raise SystemExit(f"No AI-DLC ignore block in {source}")
    replace_marked_block(
        project / ".gitignore",
        GITIGNORE_MARKER_START,
        GITIGNORE_MARKER_END,
        text[marker:],
    )


def nested_v1_install(project: Path) -> bool:
    return (
        (project / ".aidlc/aidlc-rules/VERSION").exists()
        or (project / ".aidlc/aidlc-rules/aws-aidlc-rules/core-workflow.md").exists()
    )


def is_v1_install(project: Path) -> bool:
    if (project / ".aidlc-rule-details").exists() or nested_v1_install(project):
        return True
    version_file = project / ".aidlc-version"
    return version_file.exists() and not version_file.read_text().strip().startswith("2.")


def backup_v1(project: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    backup = project.parent / f"{project.name}.aidlc-v1-backup-{stamp}"
    candidates = [
        ".aidlc", ".aidlc-rule-details", ".aidlc-version", ".gitignore",
        "CLAUDE.md", "AGENTS.md", ".cursor/rules/ai-dlc-workflow.mdc",
        ".clinerules/core-workflow.md", ".github/copilot-instructions.md",
        ".kiro/aws-aidlc-rule-details", ".kiro/steering/aws-aidlc-rules",
        ".amazonq/aws-aidlc-rule-details", ".amazonq/rules/aws-aidlc-rules",
    ]
    for relative in candidates:
        source = project / relative
        if not source.exists():
            continue
        target = backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target) if source.is_dir() else shutil.copy2(source, target)
    shutil.rmtree(project / ".aidlc-rule-details", ignore_errors=True)
    if nested_v1_install(project):
        shutil.rmtree(project / ".aidlc")
    return backup


def remove_v1_core_rule(project: Path) -> None:
    markers = (".aidlc-rule-details", ".aidlc/aidlc-rules/")
    for relative in ("CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md"):
        path = project / relative
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if any(marker in content for marker in markers):
            path.unlink()


def preserve_config(project: Path, agent: str) -> tuple[dict[str, Any] | None, str | None]:
    if agent == "claude" and (project / ".claude/settings.json").exists():
        return read_json(project / ".claude/settings.json"), None
    if agent in ("kiro", "kiro-ide") and (project / ".kiro/settings/cli.json").exists():
        return read_json(project / ".kiro/settings/cli.json"), None
    if agent == "codex" and (project / ".codex/config.toml").exists():
        return None, (project / ".codex/config.toml").read_text(encoding="utf-8")
    return None, None


def restore_config(
    project: Path,
    distribution: Path,
    agent: str,
    data: dict[str, Any] | None,
    text: str | None,
) -> None:
    if agent == "claude":
        shipped = read_json(distribution / ".claude/settings.json")
        write_json(project / ".claude/settings.json", merge_claude_settings(data or {}, shipped))
    elif agent in ("kiro", "kiro-ide") and data is not None:
        shipped = read_json(distribution / ".kiro/settings/cli.json")
        write_json(project / ".kiro/settings/cli.json", deep_defaults(data, shipped))
    elif agent == "codex" and text is not None:
        (project / ".codex/config.toml").write_text(text, encoding="utf-8")
        shutil.copy2(distribution / ".codex/config.toml", project / ".codex/config.aidlc.toml.example")


def install(project: Path, agent: str, source: Path, migrate_v1: bool) -> tuple[str, Path | None]:
    project = project.resolve()
    distribution = source / "dist" / agent
    if not distribution.is_dir():
        raise SystemExit(f"AI-DLC v2 has no distribution for {agent}")
    backup = None
    if is_v1_install(project):
        if not migrate_v1:
            raise SystemExit("AI-DLC v1 detected. Re-run with --migrate-v1 after reviewing migration limits.")
        backup = backup_v1(project)
        remove_v1_core_rule(project)
    config_data, config_text = preserve_config(project, agent)
    for directory in AGENT_DIRS[agent]:
        shutil.copytree(distribution / directory, project / directory, dirs_exist_ok=True)
    copy_missing_tree(distribution / "aidlc", project / "aidlc")
    restore_config(project, distribution, agent, config_data, config_text)
    if agent == "opencode":
        merge_opencode_config(project, distribution)
    merge_agents(project, distribution)
    merge_gitignore(project, distribution)
    version = framework_version(source)
    (project / ".aidlc-version").write_text(version + "\n", encoding="utf-8")
    return version, backup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".", help="Project directory")
    parser.add_argument("--agent", required=True, choices=sorted(AGENT_DIRS))
    parser.add_argument(
        "--migrate-v1",
        action="store_true",
        help="Back up v1 rules and install v2 fresh; v1 workflow artifacts are not converted",
    )
    args = parser.parse_args()
    project = Path(args.project)
    project.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aidlc-v2-") as temp:
        source = extract_source(Path(temp))
        version, backup = install(project, args.agent, source, args.migrate_v1)
    print(f"AI-DLC Workflows {version} installed for {args.agent}: {project.resolve()}")
    if args.agent == "claude":
        print("Claude provider, Bedrock, region, model, and effort settings were preserved; upstream runtime defaults were not installed.")
    if backup:
        print(f"V1 setup backup: {backup}")
        print("Legacy aidlc-docs/ left in place; v2 cannot resume v1 workflow state.")
    if args.agent == "codex" and (project / ".codex/config.aidlc.toml.example").exists():
        print("Merge .codex/config.aidlc.toml.example into existing .codex/config.toml.")
    print("Run the harness-specific AI-DLC doctor check in a fresh session.")


if __name__ == "__main__":
    main()

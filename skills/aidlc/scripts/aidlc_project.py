#!/usr/bin/env python3
"""Install or update AWS AI-DLC workflow rules in a project."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

RELEASE_API = "https://api.github.com/repos/awslabs/aidlc-workflows/releases/latest"
REPO_ZIP = "https://github.com/awslabs/aidlc-workflows/archive/refs/heads/main.zip"


def download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url) as response, dest.open("wb") as file:
        shutil.copyfileobj(response, file)


def latest_release_zip() -> tuple[str, str]:
    with urllib.request.urlopen(RELEASE_API) as response:
        data = json.load(response)
    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if name.startswith("ai-dlc-rules-") and name.endswith(".zip"):
            return asset["browser_download_url"], data.get("tag_name", "latest")
    return REPO_ZIP, "main"


def extract_rules(temp_dir: Path) -> tuple[Path, str]:
    url, version = latest_release_zip()
    archive = temp_dir / "aidlc.zip"
    download(url, archive)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(temp_dir / "extracted")
    candidates = list((temp_dir / "extracted").rglob("aidlc-rules"))
    if not candidates:
        raise SystemExit("Downloaded archive did not contain an aidlc-rules directory")
    return candidates[0], version


def copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def write_cursor_rule(project: Path, core_workflow: Path) -> None:
    rules_dir = project / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    target = rules_dir / "ai-dlc-workflow.mdc"
    target.write_text(
        "---\n"
        'description: "AI-DLC (AI-Driven Development Life Cycle) adaptive workflow for software development"\n'
        "alwaysApply: true\n"
        "---\n\n"
        + core_workflow.read_text(),
        encoding="utf-8",
    )


def install(project: Path, agent: str) -> list[Path]:
    project = project.resolve()
    with tempfile.TemporaryDirectory(prefix="aidlc-") as temp:
        rules, version = extract_rules(Path(temp))
        core = rules / "aws-aidlc-rules" / "core-workflow.md"
        details = rules / "aws-aidlc-rule-details"
        changed: list[Path] = []

        detail_target = project / ".aidlc-rule-details"
        copytree(details, detail_target)
        changed.append(detail_target)

        if agent == "claude":
            shutil.copy2(core, project / "CLAUDE.md")
            changed.append(project / "CLAUDE.md")
        elif agent == "claude-dir":
            (project / ".claude").mkdir(exist_ok=True)
            shutil.copy2(core, project / ".claude" / "CLAUDE.md")
            changed.append(project / ".claude" / "CLAUDE.md")
        elif agent == "codex":
            shutil.copy2(core, project / "AGENTS.md")
            changed.append(project / "AGENTS.md")
        elif agent == "cursor":
            write_cursor_rule(project, core)
            changed.append(project / ".cursor" / "rules" / "ai-dlc-workflow.mdc")
        elif agent == "cline":
            (project / ".clinerules").mkdir(exist_ok=True)
            shutil.copy2(core, project / ".clinerules" / "core-workflow.md")
            changed.append(project / ".clinerules" / "core-workflow.md")
        elif agent == "copilot":
            (project / ".github").mkdir(exist_ok=True)
            shutil.copy2(core, project / ".github" / "copilot-instructions.md")
            changed.append(project / ".github" / "copilot-instructions.md")
        elif agent == "kiro":
            steering = project / ".kiro" / "steering"
            steering.mkdir(parents=True, exist_ok=True)
            copytree(rules / "aws-aidlc-rules", steering / "aws-aidlc-rules")
            copytree(details, project / ".kiro" / "aws-aidlc-rule-details")
            changed.extend([steering / "aws-aidlc-rules", project / ".kiro" / "aws-aidlc-rule-details"])
        elif agent == "amazonq":
            qrules = project / ".amazonq" / "rules"
            qrules.mkdir(parents=True, exist_ok=True)
            copytree(rules / "aws-aidlc-rules", qrules / "aws-aidlc-rules")
            copytree(details, project / ".amazonq" / "aws-aidlc-rule-details")
            changed.extend([qrules / "aws-aidlc-rules", project / ".amazonq" / "aws-aidlc-rule-details"])
        else:
            raise SystemExit(f"Unsupported agent: {agent}")

        (project / ".aidlc-version").write_text(version + "\n", encoding="utf-8")
        changed.append(project / ".aidlc-version")
        return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", default=".", help="Project directory")
    parser.add_argument(
        "--agent",
        required=True,
        choices=["claude", "claude-dir", "codex", "cursor", "cline", "copilot", "kiro", "amazonq"],
        help="Coding agent rule format to install",
    )
    args = parser.parse_args()
    changed = install(Path(args.project), args.agent)
    print("AI-DLC files updated:")
    for path in changed:
        print(f"- {path}")


if __name__ == "__main__":
    main()

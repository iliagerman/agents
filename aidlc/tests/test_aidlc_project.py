from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "aidlc_project.py"
SPEC = importlib.util.spec_from_file_location("aidlc_project", SCRIPT)
assert SPEC and SPEC.loader
AIDLC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AIDLC)


class ClaudeSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shipped = {
            "companyAnnouncements": ["# AI-DLC — workflow"],
            "permissions": {"allow": ["Read", "Bash"]},
            "statusLine": {"type": "command", "command": "aidlc-status"},
            "env": {
                "CLAUDE_CODE_USE_BEDROCK": "1",
                "AWS_REGION": "us-east-1",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "upstream-opus",
            },
            "model": "opus[1m]",
            "effortLevel": "xhigh",
            "hooks": {
                "Stop": [
                    {
                        "hooks": [
                            {"type": "command", "command": "/project/.claude/hooks/aidlc-stop.ts"}
                        ]
                    }
                ]
            },
        }

    def test_fresh_install_omits_upstream_runtime_defaults(self) -> None:
        merged = AIDLC.merge_claude_settings({}, self.shipped)

        self.assertNotIn("env", merged)
        self.assertNotIn("model", merged)
        self.assertNotIn("effortLevel", merged)
        self.assertEqual(merged["statusLine"]["command"], "aidlc-status")
        self.assertIn("Bash", merged["permissions"]["allow"])
        self.assertIn("Stop", merged["hooks"])

    def test_existing_runtime_configuration_wins(self) -> None:
        existing = {
            "model": "user-model",
            "effortLevel": "medium",
            "env": {
                "ANTHROPIC_BASE_URL": "http://127.0.0.1:8787",
                "CLAUDE_CODE_USE_BEDROCK": "0",
            },
            "statusLine": {"type": "command", "command": "user-status"},
            "permissions": {"allow": ["Read"]},
            "hooks": {},
        }

        merged = AIDLC.merge_claude_settings(existing, self.shipped)

        self.assertEqual(merged["model"], "user-model")
        self.assertEqual(merged["effortLevel"], "medium")
        self.assertEqual(merged["env"]["ANTHROPIC_BASE_URL"], "http://127.0.0.1:8787")
        self.assertEqual(merged["env"]["CLAUDE_CODE_USE_BEDROCK"], "0")
        self.assertEqual(merged["statusLine"]["command"], "user-status")

    def test_restore_fresh_settings_replaces_copied_upstream_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            distribution = root / "dist"
            project.mkdir()
            (distribution / ".claude").mkdir(parents=True)
            (distribution / ".claude/settings.json").write_text(json.dumps(self.shipped))
            (project / ".claude").mkdir()
            (project / ".claude/settings.json").write_text(json.dumps(self.shipped))

            AIDLC.restore_config(project, distribution, "claude", None, None)
            restored = json.loads((project / ".claude/settings.json").read_text())

            self.assertNotIn("env", restored)
            self.assertNotIn("model", restored)
            self.assertNotIn("effortLevel", restored)


class MigrationTests(unittest.TestCase):
    def test_nested_v1_package_is_detected_backed_up_and_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            core = project / ".aidlc/aidlc-rules/aws-aidlc-rules/core-workflow.md"
            core.parent.mkdir(parents=True)
            core.write_text("v1 workflow")
            version = project / ".aidlc/aidlc-rules/VERSION"
            version.write_text("1.0.1\n")
            historical = project / "aidlc-docs/aidlc-state.md"
            historical.parent.mkdir(parents=True)
            historical.write_text("historical state")
            claude_rule = project / "CLAUDE.md"
            claude_rule.write_text("Read .aidlc/aidlc-rules/aws-aidlc-rules/core-workflow.md")
            agents_rule = project / "AGENTS.md"
            agents_rule.write_text("Unrelated project guidance")

            self.assertTrue(AIDLC.is_v1_install(project))
            backup = AIDLC.backup_v1(project)
            AIDLC.remove_v1_core_rule(project)

            self.assertEqual(
                (backup / ".aidlc/aidlc-rules/VERSION").read_text(),
                "1.0.1\n",
            )
            self.assertEqual(
                (backup / "CLAUDE.md").read_text(),
                "Read .aidlc/aidlc-rules/aws-aidlc-rules/core-workflow.md",
            )
            self.assertFalse((project / ".aidlc").exists())
            self.assertFalse(claude_rule.exists())
            self.assertEqual(agents_rule.read_text(), "Unrelated project guidance")
            self.assertEqual(historical.read_text(), "historical state")


if __name__ == "__main__":
    unittest.main()

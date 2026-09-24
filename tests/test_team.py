"""Platform-independent checks for routing and detached worker management."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
import unittest
import warnings
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import team  # noqa: E402


class TeamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "path with spaces"
        self.root.mkdir()
        self.db = self.root / "cc-switch.db"
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE providers (name TEXT, settings_config TEXT, app_type TEXT, is_current INTEGER)")
            conn.execute(
                "INSERT INTO providers VALUES (?, ?, ?, ?)",
                ("DeepSeek", json.dumps({"env": {
                    "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro",
                    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
                }}), "claude", 1),
            )
        self.settings = self.root / "settings.json"
        self.settings.write_text(json.dumps({"env": {
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-5",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5",
        }}), encoding="utf-8")
        self.db_patch = patch.object(team, "DB", self.db)
        self.settings_patch = patch.object(team, "CLAUDE_SETTINGS", self.settings)
        self.db_patch.start()
        self.settings_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.settings_patch.stop)

    def test_deepseek_route_does_not_require_mimo(self) -> None:
        route = team.active_route()
        self.assertEqual(route["provider"], "DeepSeek")
        self.assertEqual(team.pick_model(route, "pro")["alias"], "claude-opus-5")
        self.assertEqual(team.pick_model(route, "flash")["alias"], "claude-haiku-4-5")

    def test_explicit_mco_entry_and_missing_entry(self) -> None:
        entry = self.root / "mco"
        entry.write_text("", encoding="utf-8")
        with patch.dict(os.environ, {"MCO_ENTRY": str(entry)}):
            self.assertEqual(team.mco_command(), [sys.executable, str(entry.resolve())])
        with patch.dict(os.environ, {"MCO_ENTRY": str(self.root / "missing")}):
            with self.assertRaises(FileNotFoundError):
                team.mco_command()

    def test_windows_npm_prefix_entry_discovery(self) -> None:
        npm_bin = self.root / "npm"
        npm_bin.mkdir()
        entry = npm_bin / "node_modules" / "@tt-a1i" / "mco" / "mco"
        entry.parent.mkdir(parents=True)
        entry.write_text("", encoding="utf-8")
        launcher = npm_bin / "mco.cmd"
        launcher.write_text("", encoding="utf-8")
        with patch.dict(os.environ, {"APPDATA": str(self.root)}, clear=True):
            with patch.object(team.shutil, "which", side_effect=lambda name: str(launcher) if name == "mco" else None):
                self.assertEqual(team.mco_command(), [sys.executable, str(entry.resolve())])

    def test_background_start_status_and_result(self) -> None:
        entry = self.root / "fake_mco.py"
        entry.write_text(
            """import json, sys
from datetime import datetime, timezone
from pathlib import Path
args = sys.argv[1:]
def value(flag): return args[args.index(flag) + 1]
root = Path(value('--artifact-base')) / value('--task-id')
root.mkdir(parents=True)
answer = root / 'answer.md'
answer.write_text('READY', encoding='utf-8')
(root / 'run.json').write_text(json.dumps({'outputs': [{'invocation_id': 'worker', 'status': 'success', 'output_path': str(answer)}]}), encoding='utf-8')
now = datetime.now(timezone.utc).isoformat()
print(json.dumps({'type': 'invocation_finished', 'status': 'success', 'timestamp': now}), flush=True)
print(json.dumps({'type': 'task_finished', 'status': 'complete', 'timestamp': now}), flush=True)
""",
            encoding="utf-8",
        )
        prompt = self.root / "prompt.txt"
        prompt.write_text("Return READY", encoding="utf-8")
        args = Namespace(
            repo=str(self.root), work_dir=str(self.root / "work"), prompt_file=str(prompt),
            role="flash", expected_provider="DeepSeek", mode="read_only", alias="worker",
            timeout=10, task_id="cross-platform-probe",
        )
        with patch.dict(os.environ, {"MCO_ENTRY": str(entry)}):
            # The helper intentionally returns while its detached worker is alive.
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="subprocess .* is still running", category=ResourceWarning)
                started = team.start_task(args)
        directory = Path(started["task_dir"])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = team.show_result(directory, include_answer=True)
            if result["status"] == "complete":
                break
            time.sleep(0.05)
        self.assertEqual(result["status"], "complete", result)
        self.assertEqual(result["invocation_status"], "success")
        self.assertEqual(result["outputs"][0]["answer"], "READY")


if __name__ == "__main__":
    unittest.main()

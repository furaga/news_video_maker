"""外部サービスを呼ばずにCodex実行とスケジューラー連携を検証する。"""
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from news_video_maker import pipeline_codex

spec = importlib.util.spec_from_file_location("scheduler_under_test", ROOT / "scripts/scheduler.py")
scheduler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scheduler)


class CodexPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "prompts").mkdir()
        (self.root / "prompts/codex_pipeline.md").write_text("手順", encoding="utf-8")
        self.addCleanup(patch.stopall)
        patch.object(pipeline_codex, "PROJECT_DIR", self.root).start()
        patch.object(pipeline_codex.shutil, "which", return_value="codex.exe").start()

    def fake_cli(self, status="success", code=0, write=True):
        def execute(cmd, **kwargs):
            self.cmd, self.kwargs = cmd, kwargs
            if write:
                Path(cmd[cmd.index("--output-last-message") + 1]).write_text(
                    json.dumps({"status": status, "summary": "結果"}), encoding="utf-8")
            return SimpleNamespace(returncode=code)
        return execute

    def test_options_environment_and_stdin(self):
        original_id = os.environ.get("PIPELINE_RUN_ID")
        with patch.dict(os.environ, {"CODEX_MODEL": "configured-model"}), \
                patch.object(pipeline_codex.subprocess, "run", side_effect=self.fake_cli()):
            self.assertEqual(asyncio.run(pipeline_codex.run(True, 3, "resume_1", "2026-10-01T00:00:00Z", "paper")), 0)
        self.assertIn("workspace-write", self.cmd)
        self.assertIn("configured-model", self.cmd)
        self.assertEqual(self.cmd[-1], "-")
        self.assertEqual(self.kwargs["env"]["PIPELINE_RUN_ID"], "resume_1")
        self.assertEqual(os.environ.get("PIPELINE_RUN_ID"), original_id)
        params = json.loads(self.kwargs["input"].split("今回の実行パラメータ(JSON):\n")[1])
        self.assertEqual(params["from_stage"], 3)
        self.assertTrue(params["dry_run"])
        self.assertEqual(params["mode"], "paper")
        self.assertEqual(params["publish_at"], "2026-10-01T00:00:00Z")

    def test_failure_and_missing_result_are_not_success(self):
        for status, code, write, expected in [
            ("failed", 0, True, 1), ("success", 4, True, 1),
            ("success", 0, False, 1), ("invalid", 0, True, 1),
            ([], 0, True, 1), ("no_content", 0, True, 0),
        ]:
            with self.subTest(status=status, code=code, write=write), \
                    patch.object(pipeline_codex.subprocess, "run", side_effect=self.fake_cli(status, code, write)):
                self.assertEqual(asyncio.run(pipeline_codex.run(run_id="same_id")), expected)

    def test_invalid_id_and_missing_cli_do_not_launch(self):
        with patch.object(pipeline_codex.subprocess, "run") as launch:
            self.assertEqual(asyncio.run(pipeline_codex.run(run_id="../escape")), 1)
            with patch.object(pipeline_codex.shutil, "which", return_value=None):
                self.assertEqual(asyncio.run(pipeline_codex.run(run_id="valid")), 1)
            launch.assert_not_called()


class SchedulerTests(unittest.TestCase):
    def test_slot_forwards_codex_and_failure(self):
        with patch.object(scheduler.subprocess, "run", return_value=SimpleNamespace(returncode=1)) as launch, \
                patch.object(scheduler, "_notify_error"):
            self.assertFalse(scheduler._run_pipeline_for_slot(datetime(2026, 10, 1, tzinfo=timezone.utc), "paper", False, "codex"))
        cmd = launch.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--engine") + 1], "codex")
        self.assertEqual(cmd[cmd.index("--publish-at") + 1], "2026-10-01T00:00:00Z")

    def test_dry_run_never_generates(self):
        with patch.object(scheduler.subprocess, "run") as launch:
            self.assertTrue(scheduler._run_pipeline_for_slot(datetime.now(timezone.utc), "news", True, "codex"))
            launch.assert_not_called()

    def test_all_slots_attempted_and_failure_retained(self):
        slots = [datetime(2026, 10, 1, tzinfo=timezone.utc)] * 2
        with patch.object(scheduler, "_get_youtube_service"), \
                patch.object(scheduler, "_get_scheduled_publish_times", return_value=[]), \
                patch.object(scheduler, "_find_missing_slots", return_value=slots), \
                patch.object(scheduler, "_run_pipeline_for_slot", side_effect=[False, True]) as launch:
            self.assertFalse(scheduler.check_and_fill({"schedule": {"publish_times": ["08:00"]}}, False, "codex"))
            self.assertEqual(launch.call_count, 2)


if __name__ == "__main__":
    unittest.main()

"""Codex CLI を使ったパイプライン実行。Claude SDK には依存しない。"""
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["success", "no_content", "failed"]},
        "summary": {"type": "string"},
    },
    "required": ["status", "summary"],
    "additionalProperties": False,
}


async def run(dry_run: bool = False, from_stage: int = 1, run_id: str = "",
              publish_at: str = "", mode: str = "news") -> int:
    """既存パイプラインと同じ引数を受け、失敗時に非ゼロを返す。"""
    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        print("[Error] run-id は英数字・ハイフン・アンダースコアのみ使用できます。")
        return 1
    executable = shutil.which(os.environ.get("CODEX_BIN") or "codex")
    if not executable:
        print("[Error] Codex CLI が見つかりません。PATH または CODEX_BIN を設定してください。")
        return 1

    log_dir = PROJECT_DIR / "logs" / datetime.now().strftime("%Y%m%d")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"pipeline_codex_{run_id}.log"
    env = os.environ.copy()
    env["PIPELINE_RUN_ID"] = run_id
    env["PYTHONIOENCODING"] = "utf-8"
    # ツールのキャッシュも書き込み可能なプロジェクト配下に収める。
    cache_dir = PROJECT_DIR / ".cache" / "codex-tools"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for key, folder in (("UV_CACHE_DIR", "uv"), ("HF_HOME", "huggingface"),
                        ("TORCH_HOME", "torch")):
        env.setdefault(key, str(cache_dir / folder))
    parameters = dict(run_id=run_id, from_stage=from_stage, dry_run=dry_run,
                      publish_at=publish_at, mode=mode)
    try:
        prompt = (PROJECT_DIR / "prompts" / "codex_pipeline.md").read_text(encoding="utf-8")
        prompt += "\n\n今回の実行パラメータ(JSON):\n" + json.dumps(parameters, ensure_ascii=False)
        # 再開時にも古い成功結果が残らないよう、実行ごとの一時ファイルを使う。
        with tempfile.TemporaryDirectory(prefix="codex-", dir=log_dir) as temp:
            schema_path = Path(temp) / "schema.json"
            result_path = Path(temp) / "result.json"
            schema_path.write_text(json.dumps(RESULT_SCHEMA), encoding="utf-8")
            cmd = [executable, "--search", "--ask-for-approval", "never", "exec",
                   "--cd", str(PROJECT_DIR), "--sandbox", "workspace-write",
                   "-c", "sandbox_workspace_write.network_access=true",
                   "-c", 'shell_environment_policy.inherit="all"',
                   "--color", "never", "--output-schema", str(schema_path),
                   "--output-last-message", str(result_path)]
            if os.environ.get("CODEX_MODEL"):
                cmd.extend(["--model", os.environ["CODEX_MODEL"]])
            cmd.append("-")
            print(f"[Codex] run_id={run_id} log={log_path}", flush=True)
            with log_path.open("a", encoding="utf-8") as log:
                log.write(f"\n=== {datetime.now().isoformat()} {json.dumps(parameters)} ===\n")
                log.flush()
                completed = subprocess.run(cmd, input=prompt, encoding="utf-8",
                                           stdout=log, stderr=subprocess.STDOUT,
                                           cwd=PROJECT_DIR, env=env, check=False)
            if completed.returncode != 0:
                print(f"[Error] Codex CLI exit={completed.returncode}; {log_path}")
                return 1
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if (not isinstance(result, dict)
                    or result.get("status") not in ("success", "no_content", "failed")
                    or not isinstance(result.get("summary"), str)):
                raise ValueError("Codex の最終結果が不正です")
            with log_path.open("a", encoding="utf-8") as log:
                log.write("\n[Result] " + json.dumps(result, ensure_ascii=False) + "\n")
            print(f"[Codex] {result['status']}: {result['summary']}", flush=True)
            return 0 if result["status"] in {"success", "no_content"} else 1
    except (OSError, ValueError) as exc:
        print(f"[Error] Codex パイプライン: {exc}", flush=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[Error] {exc}\n")
        return 1

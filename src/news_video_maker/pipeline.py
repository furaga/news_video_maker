"""Claude Agent SDK を使ったパイプライン実行オーケストレーター"""
import os
from datetime import datetime

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)
from claude_agent_sdk.types import TextBlock, ToolUseBlock

PROJECT_DIR = str(__file__.replace("\\", "/").split("src/")[0].rstrip("/"))


def _log(msg: str, file) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    print(line, file=file, flush=True)


def _summarize_tool_input(name: str, inp: dict) -> str:
    if name == "Bash":
        return inp.get("command", "")[:80].replace("\n", " ")
    if name in ("Read", "Write", "Edit", "Glob", "Grep"):
        return inp.get("file_path") or inp.get("pattern") or str(inp)[:60]
    return str(inp)[:60]


async def run(dry_run: bool = False, from_stage: int = 1, run_id: str = "") -> int:
    """パイプラインを実行して終了コードを返す"""
    # 実行IDを生成してキャッシュディレクトリを分離（並列実行対応）
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.environ["PIPELINE_RUN_ID"] = run_id

    args_parts = [f"--run-id {run_id}"]
    if from_stage > 1:
        args_parts.append(f"--from-stage {from_stage}")
    if dry_run:
        args_parts.append("--dry-run")
    prompt = f"/run-pipeline {' '.join(args_parts)}".strip()

    now = datetime.now()
    log_dir = os.path.join(PROJECT_DIR, "logs", now.strftime("%Y%m%d"))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"pipeline_{run_id}.log")

    options = ClaudeAgentOptions(
        cwd=PROJECT_DIR,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="bypassPermissions",
        setting_sources=["project"],
        max_turns=50,
    )

    exit_code = 0
    log_file = open(log_path, "w", encoding="utf-8", buffering=1)
    try:
        _log(f"=== パイプライン開始 run_id={run_id} from_stage={from_stage} dry_run={dry_run} ===", log_file)
        _log(f"ログ: {log_path}", log_file)
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text = block.text.replace("\n", " ")[:120]
                        _log(f"[Claude] {text}", log_file)
                    elif isinstance(block, ToolUseBlock):
                        summary = _summarize_tool_input(block.name, block.input)
                        _log(f"[Tool]   {block.name}: {summary}", log_file)
            elif isinstance(message, SystemMessage):
                _log(f"[System] subtype={message.subtype}", log_file)
            elif isinstance(message, ResultMessage):
                status = "ERROR" if message.is_error else "OK"
                cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd else "n/a"
                secs = message.duration_ms // 1000
                _log(f"[Done]   status={status} turns={message.num_turns} cost={cost} time={secs}s", log_file)
                if message.result:
                    print(message.result, flush=True)
    except Exception as e:
        _log(f"[Error] パイプライン実行エラー: {e}", log_file)
        exit_code = 1
    finally:
        log_file.close()

    return exit_code

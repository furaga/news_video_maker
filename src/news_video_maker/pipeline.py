"""Claude Agent SDK を使ったパイプライン実行オーケストレーター"""
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import anyio
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)
from claude_agent_sdk.types import TextBlock, ToolUseBlock

PROJECT_DIR = str(__file__.replace("\\", "/").split("src/")[0].rstrip("/"))
COMMANDS_DIR = os.path.join(PROJECT_DIR, ".claude", "commands")

# サブエージェント共通の前置き。コマンドファイル中の `.cache/pipeline/` パスを run_id 配下に読み替えさせる
_SUBAGENT_PREAMBLE = (
    "あなたはニュース動画パイプラインの1ステージを担当するサブエージェントです。\n"
    "呼び出し元から run_id が渡されるので、以下の手順中の `.cache/pipeline/` は "
    "`.cache/pipeline/{run_id}/` に読み替えて実行してください。\n"
    "手順を完了したら、結果の要点（生成したファイルのパスと OK/NG）だけを短く報告してください。\n\n---\n\n"
)


def _load_command(name: str) -> str:
    """`.claude/commands/<name>.md` をサブエージェントのプロンプトとして読み込む"""
    with open(os.path.join(COMMANDS_DIR, f"{name}.md"), encoding="utf-8") as f:
        return _SUBAGENT_PREAMBLE + f.read()


def _build_subagents() -> dict[str, AgentDefinition]:
    """軽いモデルで実行するステージをサブエージェントとして定義する。

    サブエージェントのコンテキスト（画像・WebSearch 結果など）は親セッションに戻らないため、
    モデル単価の削減に加えて、親（opus）の以降のターンで再送されるトークンも減る。
    """
    return {
        "video-checker": AgentDefinition(
            description="動画フレーム画像を目視確認して visual_check を 04_validation.json に追記する",
            prompt=_load_command("validate-video"),
            tools=["Read", "Write", "Glob"],
            model="haiku",
        ),
        "metadata-writer": AgentDefinition(
            description="YouTube 投稿用メタデータ (05_metadata.json) と投稿者コメント (05_comment.txt) を生成する",
            prompt=_load_command("generate-metadata"),
            tools=["Read", "Write", "WebSearch", "WebFetch"],
            model="sonnet",
        ),
    }


def _log(msg: str, file) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    print(line, file=file, flush=True)


def _format_usage(usage: dict | None) -> str:
    """ResultMessage.usage をログ用に整形する（before/after 比較のため）"""
    if not usage:
        return "usage=n/a"
    return (
        f"in={usage.get('input_tokens', 0)} "
        f"cache_w={usage.get('cache_creation_input_tokens', 0)} "
        f"cache_r={usage.get('cache_read_input_tokens', 0)} "
        f"out={usage.get('output_tokens', 0)}"
    )


def _summarize_tool_input(name: str, inp: dict) -> str:
    if name == "Bash":
        return inp.get("command", "")[:80].replace("\n", " ")
    if name in ("Read", "Write", "Edit", "Glob", "Grep"):
        return inp.get("file_path") or inp.get("pattern") or str(inp)[:60]
    return str(inp)[:60]


async def run(dry_run: bool = False, from_stage: int = 1, run_id: str = "", publish_at: str = "", mode: str = "news") -> int:
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
    if publish_at:
        args_parts.append(f"--publish-at {publish_at}")
    if mode and mode != "news":
        args_parts.append(f"--mode {mode}")
    prompt = f"/run-pipeline {' '.join(args_parts)}".strip()

    now = datetime.now()
    log_dir = os.path.join(PROJECT_DIR, "logs", now.strftime("%Y%m%d"))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"pipeline_{run_id}.log")

    options = ClaudeAgentOptions(
        cwd=PROJECT_DIR,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Agent"],
        permission_mode="bypassPermissions",
        setting_sources=["project"],
        max_turns=50,
        model="opus",
        agents=_build_subagents(),
    )

    exit_code = 0
    log_file = open(log_path, "w", encoding="utf-8", buffering=1)
    try:
        _log(f"=== パイプライン開始 run_id={run_id} from_stage={from_stage} dry_run={dry_run} publish_at={publish_at} mode={mode} ===", log_file)
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
                _log(f"[Usage]  {_format_usage(message.usage)}", log_file)
                if message.result:
                    print(message.result, flush=True)
    except Exception as e:
        _log(f"[Error] パイプライン実行エラー: {e}", log_file)
        exit_code = 1
    finally:
        log_file.close()

    return exit_code

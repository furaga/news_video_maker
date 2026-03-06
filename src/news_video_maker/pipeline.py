"""Claude Agent SDK を使ったパイプライン実行オーケストレーター"""
import anyio
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

PROJECT_DIR = str(__file__.replace("\\", "/").split("src/")[0].rstrip("/"))


async def run(dry_run: bool = False, from_stage: int = 1) -> int:
    """パイプラインを実行して終了コードを返す"""
    # オプションを引数文字列に変換
    args_parts = []
    if from_stage > 1:
        args_parts.append(f"--from-stage {from_stage}")
    if dry_run:
        args_parts.append("--dry-run")
    args_str = " ".join(args_parts)

    prompt = f"/run-pipeline {args_str}".strip()

    options = ClaudeAgentOptions(
        cwd=PROJECT_DIR,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        setting_sources=["project"],
        max_turns=50,
    )

    exit_code = 0
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                print(message.result)
    except Exception as e:
        print(f"パイプライン実行エラー: {e}")
        exit_code = 1

    return exit_code

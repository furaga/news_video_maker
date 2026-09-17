# Codex版パイプライン

- `scripts/scheduler_codex.bat` はプロジェクトルートで `uv run python scripts/scheduler.py --once --engine codex` を実行する。追加引数を転送し、ログは `logs/scheduler_codex.log` に追記、終了コードを呼び出し元へ返す。
- scheduler と run_pipeline に `--engine {claude,codex}` を追加する。既定値は claude。Codex 選択時には Claude SDK を読み込まない。
- 予約枠の計算・YouTube 認証・生成ツール・既存設定は共用する。スロットの失敗は単発スケジューラーの終了コード1に反映する。
- Codex CLI の `exec` に UTF-8 の標準入力で手順を渡す。workspace-write、ネットワーク許可、承認待ちなしで実行する。書き込み範囲はプロジェクトと専用ツールキャッシュ。権限不足は失敗として扱う。
- `CODEX_BIN` で実行ファイル、`CODEX_MODEL` でモデルを任意指定できる。未指定時は PATH の codex と CLI の既定モデルを使う。実行ユーザーで事前に `codex login` が必要。
- Codex用の統合手順は `prompts/codex_pipeline.md`。選定・台本・視覚検証・メタデータの品質基準とスキーマは既存 `.claude/commands/` を共用し、Codexのツールで直接実行する。
- news / paper、from-stage、run-id、publish-at、dry-run を保持。scheduler の dry-run は生成なし、pipeline の dry-run は生成あり・アップロードとコメント投稿なし。
- run-id はパスの1要素に制限。生成時はマイクロ秒を含める。PIPELINE_RUN_ID は子プロセスにのみ設定する。
- stdout/stderr は日付別ログへ記録。最終JSONは success / no_content / failed と summary を必須とし、CLIエラー、結果欠落、不正結果、failed は終了コード1。古い結果を再利用しない。
- 自動テストではCodex・YouTubeをモックし、投稿・動画生成・AI利用は実行しない。

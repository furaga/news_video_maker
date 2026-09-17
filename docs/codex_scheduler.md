# Codex版スケジューラー

既存の `scripts/scheduler.bat` は引き続きClaude版です。
Codex版は同じプロジェクトの `scripts/scheduler_codex.bat` を起動します。
予約枠、`.env`、VOICEVOX、YouTube認証などは従来の設定を共用します。

## 準備

実行するWindowsユーザーで `codex --version` と `codex login status` を確認します。
未ログインなら `codex login` を実行してください。
PATHで見つからない場合、環境変数 `CODEX_BIN` にCodexの実行ファイルのフルパスを指定できます。
モデルを固定する場合は `CODEX_MODEL` を設定します。省略時はCodex CLIの設定を使います。
Claudeのopus/sonnet/haiku指定はCodex版には適用しません。

```bat
scripts\scheduler_codex.bat
```

タスクスケジューラーからはこのバッチのフルパスを指定します。
この変更でタスクの登録や実際の投稿は行いません。

## 確認と個別実行

```bat
rem YouTubeの予約状況確認のみ。動画生成・投稿なし（YouTube認証は必要）
scripts\scheduler_codex.bat --dry-run

rem 個別に動画を生成・検証する。アップロードとコメント投稿はスキップ
uv run python scripts/run_pipeline.py --engine codex --dry-run

rem 論文モード
uv run python scripts/run_pipeline.py --engine codex --mode paper --dry-run

rem 指定実行のステージ3から再開
uv run python scripts/run_pipeline.py --engine codex --run-id example_1 --from-stage 3 --dry-run
```

`scheduler` の `--dry-run` と `run_pipeline` の `--dry-run` は上記の通り動作が異なります。
スケジューラーは `config/schedule.yml` のモード・予約時刻を使います。

## ログと権限

- スケジューラー: `logs/scheduler_codex.log`
- Codex詳細: `logs/YYYYMMDD/pipeline_codex_<run_id>.log`
- 生成結果: `report.md`
- 終了コード: 成功・新規なしは0、CLIやパイプラインの失敗は1。

Codexはworkspace-writeサンドボックスとネットワーク許可で実行します。
承認ダイアログでは待機せず、権限不足はログに残して失敗します。
uv・Hugging Face・Torchのキャッシュは、対応する環境変数が未指定なら
`.cache/codex-tools/` 配下を使います。初回はモデルなどの再ダウンロードが必要になる場合があります。
独自のキャッシュ場所を指定した場合は、その場所への書き込み権限も必要です。

Codexの非対話実行と構造化出力:
https://learn.chatgpt.com/docs/non-interactive-mode

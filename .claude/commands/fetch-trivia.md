# /fetch-trivia

OpenTDB から雑学・豆知識クイズデータを取得して `.cache/pipeline/{run_id}/01_trivia.json` に保存する。

## 手順

Bash ツールで以下を実行:
```bash
cd /c/Users/furag/Documents/prog/python/wt-new-themes && uv run python -m news_video_maker.fetcher.trivia
```

（`PIPELINE_RUN_ID` 環境変数が設定済みのため、Python側が自動的に正しいディレクトリへ書き込む）

実行後、取得件数と保存先を報告する。

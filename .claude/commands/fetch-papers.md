# /fetch-papers

arXiv と HF Daily Papers から最新の技術論文を取得して `.cache/pipeline/01_papers.json` に保存する。

## 手順

Bash ツールで以下を実行:

```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.fetcher.paper
```

実行後、取得件数（全件・HF掲載件数）と保存先を報告する。
エラーが発生した場合はエラー内容を表示して停止する。

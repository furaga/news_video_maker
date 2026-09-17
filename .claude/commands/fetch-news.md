# /fetch-news

RSSフィードから最新のテックニュース記事を取得して `.cache/pipeline/01_articles.json` に保存する。
同時に、選定用の軽量版（`full_text` を除いたもの）を `.cache/pipeline/01_articles_index.json` に保存する。

## 手順

Bash ツールで以下を実行:

```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.fetcher.rss
```

実行後、取得件数と保存先を報告する。
エラーが発生した場合はエラー内容を表示して停止する。

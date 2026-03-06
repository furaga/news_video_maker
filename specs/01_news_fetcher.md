# 仕様書: ニュース取得（News Fetcher）

## 目的

海外技術ニュースサイトの RSS/Atom フィードから最新記事を取得し、後続ステージで処理可能な形式に変換する。

## 対応コマンド

`.claude/commands/fetch-news.md` → `/fetch-news`

## 担当

Python（feedparser + httpx）

---

## 入力

設定ファイル（`src/news_video_maker/config.py`）から以下を読み込む:

- `feeds`: RSSフィードURL一覧
- `fetch_hours`: 何時間以内の記事を取得するか（デフォルト: 24）
- `max_articles`: 最大取得件数（デフォルト: 30）

### 対象フィード

| ソース | URL |
|---|---|
| Hacker News (人気記事) | `https://hnrss.org/newest?points=100` |
| TechCrunch | `https://techcrunch.com/feed/` |
| The Verge | `https://www.theverge.com/rss/index.xml` |
| Ars Technica | `https://feeds.arstechnica.com/arstechnica/index` |

---

## 出力

**ファイル**: `.cache/pipeline/01_articles.json`

**スキーマ**（`NewsArticle` のリスト）:

```json
[
  {
    "title": "記事タイトル（英語）",
    "url": "https://...",
    "source": "hackernews",
    "published_at": "2026-03-07T10:00:00Z",
    "summary_text": "RSS から取得した要約テキスト（英語）",
    "full_text": ""
  }
]
```

- `full_text`: RSS の要約が 200 文字未満の場合、httpx で本文を別途取得して格納する。それ以外は空文字列。

---

## データモデル

`src/news_video_maker/fetcher/models.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class NewsArticle:
    title: str
    url: str
    source: str          # "hackernews" | "techcrunch" | "theverge" | "arstechnica"
    published_at: datetime
    summary_text: str
    full_text: str = ""
```

---

## 振る舞い

1. 設定から RSS フィード URL 一覧を取得
2. 各フィードを feedparser で並列取得（または順次取得）
3. エントリをフィルタリング
   - `published_at` が指定時間内のもののみ
   - URL で重複除去
4. 各エントリを `NewsArticle` に変換
5. `summary_text` が 200 文字未満なら httpx で本文取得を試みる（タイムアウト: 10秒）
6. `published_at` 降順でソート
7. 上位 `max_articles` 件を `.cache/pipeline/01_articles.json` に保存

---

## エラー処理

- **個別フィードの失敗**: 警告ログを出力し、他フィードの処理を継続する（1フィードの失敗でパイプラインを止めない）
- **HTTP タイムアウト**: 本文取得時のタイムアウトは 10 秒。失敗した場合は `full_text` を空文字列のままにする
- **日時パース失敗**: `published_at` のパースに失敗したエントリはスキップする
- **0件取得**: 全フィードが失敗した場合はエラーを raise し、パイプラインを停止する

---

## 実装ノート

- `feedparser` でのエントリ日時フィールドは `entry.published_parsed` または `entry.updated_parsed`（どちらかが存在する）
- `source` フィールドはフィード URL から判別する（例: `techcrunch.com` → `"techcrunch"`）
- 本文取得時は `httpx.get()` の `headers={"User-Agent": "news-video-maker/0.1"}` を設定する
- ライブラリドキュメント参照: `use context7` で `feedparser`, `httpx` を検索

---

## テスト方針

- `tests/fetcher/test_rss.py`
- フィード取得はモック（`pytest-mock`）を使用
- 正常系: 複数フィードから記事取得できること
- 異常系: 1フィード失敗でも他のフィードから取得できること
- 異常系: 全フィード失敗時に例外が発生すること

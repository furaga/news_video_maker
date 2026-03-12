# 仕様書: 宇宙ニュースフェッチャー (01d)

## 概要

NASA APOD API と NASA ニュース RSS から宇宙・天文コンテンツを取得し、
`.cache/pipeline/{run_id}/01_space.json` に保存する。

## コンポーネント

- **モジュール**: `src/news_video_maker/fetcher/space.py`
- **実行方法**: `uv run python -m news_video_maker.fetcher.space`
- **出力**: `.cache/pipeline/{run_id}/01_space.json`

## 入力

なし（HTTP API から直接取得）

## ソース

### 1. NASA APOD (Astronomy Picture of the Day)

```
https://api.nasa.gov/planetary/apod?api_key={NASA_API_KEY}&count=10
```

- `NASA_API_KEY` が未設定の場合は `DEMO_KEY` を使用（50 req/日の制限あり）
- `media_type == "image"` のみ使用（`"video"` は除外）
- `url` フィールドが背景画像として使える高品質 NASA 画像 URL

### 2. NASA Breaking News RSS

```
https://www.nasa.gov/rss/dyn/breaking_news.rss
```

- `feedparser` でパース（既存 `rss.py` と同じ手法）
- `enclosure` タグから `image_url` を取得（なければ空文字）
- 直近 7 日以内の記事のみ取得

## 処理

1. APOD API から 10 件取得（`media_type == "image"` でフィルター）
2. NASA RSS から最新記事を取得
3. `HistoryStore` で重複除外（キー: `url`）
4. APOD 優先でソート（NASA 公式画像を確実に含める）

## 出力スキーマ

```json
[
  {
    "title": "The Pillars of Creation",
    "url": "https://apod.nasa.gov/apod/ap231012.html",
    "source": "nasa_apod",
    "published_at": "2023-10-12T00:00:00Z",
    "description": "These towering pillars of cosmic dust and gas...",
    "image_url": "https://apod.nasa.gov/apod/image/2310/pillars_jwst.jpg",
    "media_type": "image"
  }
]
```

| フィールド | 説明 |
|---|---|
| `title` | コンテンツタイトル（英語） |
| `url` | ページ URL（APOD ページ or RSS 記事 URL） |
| `source` | `nasa_apod` または `nasa_rss` |
| `published_at` | 公開日時（ISO 8601 UTC） |
| `description` | 説明文（英語、1000 文字以内） |
| `image_url` | 背景画像として使用可能な直接 URL |
| `media_type` | `image` のみ（video は除外済み） |

## エラー処理

- APOD API エラー: ログ警告を出力して RSS のみ使用
- RSS エラー: ログ警告を出力して APOD のみ使用
- 両方失敗: 空リストを保存して `"新規宇宙コンテンツなし"` を出力
- DEMO_KEY レート超過（429）: エラーログを出力し RSS のみで継続

## 出力確認

```
取得完了: XX 件（APOD: X件, RSS: X件）→ .cache/pipeline/{run_id}/01_space.json
```

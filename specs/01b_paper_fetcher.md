# 仕様書: 論文フェッチャー (paper_fetcher)

## 概要

arXiv API と Hugging Face Daily Papers API から最新の技術論文を取得し、`.cache/pipeline/{run_id}/01_papers.json` に保存する。

## 取得元

### 1. arXiv API

- エンドポイント: `http://export.arxiv.org/api/query`
- 対象カテゴリ: `cs.AI`, `cs.LG`, `cs.CV`, `cs.RO`
- クエリ: `cat:cs.AI OR cat:cs.LG OR cat:cs.CV OR cat:cs.RO`
- ソート: `submittedDate` 降順
- 取得件数: 最大 `MAX_PAPERS`（デフォルト 50）件
- フィルタ: 投稿日が現在から `PAPER_FETCH_DAYS`（デフォルト 2）日以内のもののみ
- パーサー: `feedparser`（既存の RSS フェッチャーと同一ライブラリ）

### 2. Hugging Face Daily Papers API

- エンドポイント: `https://huggingface.co/api/daily_papers?date=YYYY-MM-DD`
- 取得日: 本日と前日の 2 日分
- レスポンス: JSON 配列（`paper.id` に arXiv ID、`totalUpvotes` に総投票数）
- 目的: arXiv 取得結果の論文に HF 掲載フラグ・upvotes 数を付与するクロスリファレンス

## 重複除外

- `.cache/history.json` の `HistoryStore.seen_urls()` を使用
- `arxiv_url`（例: `https://arxiv.org/abs/2603.06199`）が履歴に含まれる論文はスキップ

## 出力スキーマ

`.cache/pipeline/{run_id}/01_papers.json`

```json
[
  {
    "paper_id": "2603.06199",
    "title": "FlashPrefill: Instantaneous Pattern Discovery...",
    "authors": ["Qihang Fan", "Huaibo Huang"],
    "abstract": "論文の要旨（原文英語、最大 1000 文字）",
    "arxiv_url": "https://arxiv.org/abs/2603.06199",
    "pdf_url": "https://arxiv.org/pdf/2603.06199",
    "categories": ["cs.AI", "cs.LG"],
    "submitted_at": "2026-03-06T00:00:00+00:00",
    "hf_featured": true,
    "hf_upvotes": 15,
    "image_url": ""
  }
]
```

### フィールド定義

| フィールド | 型 | 説明 |
|---|---|---|
| `paper_id` | str | arXiv 論文ID（例: `2603.06199`） |
| `title` | str | 論文タイトル（英語原文） |
| `authors` | list[str] | 著者リスト（最大 5 名、それ以降は省略） |
| `abstract` | str | 要旨（英語、1000 文字以内に切り詰め） |
| `arxiv_url` | str | arXiv 論文ページの URL |
| `pdf_url` | str | PDF 直リンク |
| `categories` | list[str] | arXiv カテゴリ（例: `["cs.AI", "cs.LG"]`） |
| `submitted_at` | str | ISO 8601 形式の投稿日時 |
| `hf_featured` | bool | HF Daily Papers に掲載されていれば `true` |
| `hf_upvotes` | int | HF での総 upvote 数（未掲載は `0`） |
| `image_url` | str | 常に空文字（論文モードでは使用しない） |

## エラー処理

- arXiv API がタイムアウト（10 秒）または HTTP エラーの場合: エラーを表示して空リストを返す
- HF API が失敗した場合: HF 情報なしで継続（全論文を `hf_featured: false, hf_upvotes: 0` とする）
- 取得結果が 0 件の場合: 空リスト `[]` を保存して終了（パイプラインは「新規論文なし」として停止）

## 設定値（config.py）

| 定数 | デフォルト値 | 説明 |
|---|---|---|
| `PAPER_FETCH_DAYS` | `2` | 何日前までの論文を取得するか |
| `MAX_PAPERS` | `50` | 最大取得件数 |
| `ARXIV_CATEGORIES` | `["cs.AI", "cs.LG", "cs.CV", "cs.RO"]` | 対象カテゴリ |

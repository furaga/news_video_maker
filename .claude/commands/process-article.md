# /process

`.cache/pipeline/01_articles.json` の記事一覧から最も面白い記事を1件選定し、日本語要約して `.cache/pipeline/02_selected.json` に保存する。

## 手順

1. Read ツールで `.cache/pipeline/01_articles.json` を読み込む

2. 全記事をスコアリング（1〜10）:
   - 技術的に興味深いか（新技術・革新的手法など）
   - 日本のエンジニアに関係があるか
   - 日常的に使うツール・サービスの重要なアップデートか
   - 実質的な内容があるか（センセーショナルすぎない）

3. 最高スコアの記事を1件選定（同点は新しい方を優先）

4. 選定記事の `image_url` フィールドを `01_articles.json` からそのまま引き継ぐ

5. 選定記事を日本語で処理:
   - `japanese_title`: 元タイトルを自然な日本語に意訳（40文字以内）
   - `japanese_summary`: 記事内容を日本語で詳しく要約（200〜300文字）
   - `key_points`: 動画スクリプト用の箇条書き3〜5個（各40文字以内）

6. Write ツールで `.cache/pipeline/02_selected.json` に以下のスキーマで保存:

```json
{
  "title": "元の英語タイトル",
  "url": "https://...",
  "source": "techcrunch",
  "image_url": "https://... (01_articles.json の image_url をそのまま引き継ぐ。なければ空文字)",
  "japanese_title": "日本語タイトル（40文字以内）",
  "japanese_summary": "日本語の詳細要約（200〜300文字）",
  "interest_score": 8.5,
  "key_points": [
    "ポイント1（1文、40文字以内）",
    "ポイント2（1文、40文字以内）",
    "ポイント3（1文、40文字以内）"
  ]
}
```

## エラー処理

- `01_articles.json` が空の場合はエラーを表示して停止する
- JSONが正しく生成できない場合は最大2回まで再試行する

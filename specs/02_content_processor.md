# 仕様書: コンテンツ処理（Content Processor）

## 目的

フェッチした記事一覧から最も面白い記事を1件選定し、日本語で詳細要約する。処理は Claude Code（LLM）が担当する。

## 対応コマンド

`.claude/commands/process-article.md` → `/process`

## 担当

Claude Code（LLM処理）

---

## 入力

**ファイル**: `.cache/pipeline/01_articles.json`（`specs/01_news_fetcher.md` の出力）

---

## 出力

**ファイル**: `.cache/pipeline/02_selected.json`

**スキーマ**（`ProcessedArticle`）:

```json
{
  "title": "元の英語タイトル",
  "url": "https://...",
  "source": "techcrunch",
  "japanese_title": "日本語タイトル（40文字以内）",
  "japanese_summary": "日本語の詳細要約（200〜300文字）",
  "interest_score": 8.5,
  "key_points": [
    "ポイント1（1文、40文字以内）",
    "ポイント2（1文、40文字以内）",
    "ポイント3（1文、40文字以内）"
  ],
  "related_research": "WebSearchで調査した関連情報・背景情報（200〜300文字）"
}
```

---

## データモデル

`src/news_video_maker/processor/` 以下のモデルとして定義（実装時に追加）:

```python
from dataclasses import dataclass

@dataclass
class ProcessedArticle:
    title: str
    url: str
    source: str
    japanese_title: str
    japanese_summary: str
    interest_score: float
    key_points: list[str]
    related_research: str  # WebSearchで調査した関連情報
```

---

## 振る舞い

### ステップ1: 記事のスコアリング

`01_articles.json` の全記事タイトルと要約（先頭 300 文字）を読み込み、Claude が以下の観点で 1〜10 でスコアを付ける:

**スコアリング観点（日本語テック読者向け）:**
- 技術的に興味深いか（新技術・革新的手法など）
- 日本のエンジニアに関係があるか
- 日常的に使うツール・サービスに関する重要なアップデートか
- センセーショナルすぎず、実質的な内容があるか

### ステップ2: 最高スコアの記事を選定

スコアが最も高い記事を1件選ぶ。同点の場合は新しい記事を優先。

### ステップ3: 日本語要約の生成

選定した記事の `summary_text`（または `full_text` がある場合はその先頭 2000 文字）を元に:

1. **`japanese_title`**: 元タイトルを自然な日本語に意訳（40文字以内）
2. **`japanese_summary`**: 記事の内容を日本語で詳しく要約（200〜300文字）
   - 技術的な背景・意義を含める
   - 専門用語はそのまま使い、必要に応じて括弧で英語表記を補足
3. **`key_points`**: 動画スクリプトで使う3〜5個の箇条書きポイント（各40文字以内）

### ステップ4: 関連情報の調査

`WebSearch` ツールを使い、選定記事のトピックに関連する情報を2〜3回検索する:

- 目的: 視聴者（日本のエンジニア）にとって有益な補足情報を提供し、単なる記事の読み上げではない深みのある動画にする
- 検索例: 類似事例・比較技術・業界背景・専門家コメント・今後の動向など
- 収集した情報を `related_research` フィールドに日本語でまとめる（200〜300文字）

---

## エラー処理

- `01_articles.json` が空の場合はエラーを raise してパイプラインを停止する
- スコアリング結果が JSON として正しく解釈できない場合は再度試みる（最大2回）
- 要約生成に失敗した場合は次点の記事を試みる

---

## コマンド実装ノート（`.claude/commands/process-article.md`）

Claude Code コマンドとして実装するため、コマンドファイル内で:

1. `Read` ツールで `.cache/pipeline/01_articles.json` を読み込む
2. Claude 自身がスコアリングと選定を判断する
3. `WebSearch` ツールで関連情報を2〜3回調査する
4. `Write` ツールで `.cache/pipeline/02_selected.json` を保存する

Python ツールへの依存はなし（Claude が直接 JSON を生成する）。

---

## テスト方針

このステージは Claude Code（LLM）が処理するため、ユニットテストではなくコマンド実行による E2E テストで確認する:

- 正常系: `01_articles.json` から `02_selected.json` が生成されること
- 出力が JSON スキーマに準拠していること
- `key_points` が 3〜5 件であること
- `interest_score` が 1.0〜10.0 の範囲であること
- `related_research` フィールドが存在し、空でないこと

# 仕様書: 雑学フェッチャー (01c)

## 概要

Open Trivia Database (OpenTDB) から雑学・豆知識クイズデータを取得し、
`.cache/pipeline/{run_id}/01_trivia.json` に保存する。

## コンポーネント

- **モジュール**: `src/news_video_maker/fetcher/trivia.py`
- **実行方法**: `uv run python -m news_video_maker.fetcher.trivia`
- **出力**: `.cache/pipeline/{run_id}/01_trivia.json`

## 入力

なし（HTTP API から直接取得）

## 処理

### 1. カテゴリ別取得

以下のカテゴリから各 10 件を取得:

| カテゴリID | カテゴリ名 |
|---|---|
| 17 | Science & Nature（科学・自然） |
| 20 | Mythology（神話） |
| 22 | Geography（地理） |
| 23 | History（歴史） |
| 27 | Animals（動物） |

エンドポイント:
```
https://opentdb.com/api.php?amount=10&category={ID}&type=multiple
```

### 2. HTML エンティティのデコード

OpenTDB はすべてのテキストフィールドを HTML エンコードして返す。
`html.unescape()` で必ずデコードする（例: `&amp;` → `&`, `&#039;` → `'`）。

### 3. 重複除外

`HistoryStore` を使用して既出の質問をスキップ。
ヒストリキーは `opentdb://{sha256(question_text)[:16]}` 形式（URLの代わり）。

### 4. カテゴリ間 sleep

OpenTDB のレート制限対策として、カテゴリ間に 1 秒の sleep を入れる。

## 出力スキーマ

```json
[
  {
    "question": "What is the most common blood type in the world?",
    "correct_answer": "O+",
    "incorrect_answers": ["A+", "B+", "AB+"],
    "category": "Science: Humans",
    "difficulty": "easy",
    "image_url": "",
    "url": "opentdb://a1b2c3d4e5f6g7h8"
  }
]
```

| フィールド | 説明 |
|---|---|
| `question` | 質問文（HTML デコード済み） |
| `correct_answer` | 正解（HTML デコード済み） |
| `incorrect_answers` | 不正解の選択肢（HTML デコード済み） |
| `category` | OpenTDB カテゴリ名 |
| `difficulty` | `easy` / `medium` / `hard` |
| `image_url` | 空文字列（後続ステージで補完） |
| `url` | `opentdb://` スキームの一意キー（重複防止用） |

## エラー処理

- HTTP エラー・タイムアウト: ログに警告を出力してそのカテゴリをスキップ（他カテゴリは継続）
- 全カテゴリ失敗: 空リストを保存して `"新規雑学なし"` を出力

## 出力確認

```
取得完了: XX 件 → .cache/pipeline/{run_id}/01_trivia.json
```

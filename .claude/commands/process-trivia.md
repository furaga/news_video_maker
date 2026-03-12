# /process-trivia

雑学データから最も動画映えする1件を選定し、日本語コンテンツを生成して `02_selected.json` に保存する。

## 手順

### 1. 過去採用タイトルを取得（ネタ被り防止）

```bash
ls .cache/pipeline/*/02_selected.json 2>/dev/null
```

現在の `{run_id}` 以外のファイルを Read ツールで読み込み、`title` と `japanese_title` を `past_titles` リストとして収集する。ファイルがなければ `past_titles = []`。

### 2. 雑学データをスコアリングして最良の1件を選定

Read ツールで `.cache/pipeline/{run_id}/01_trivia.json` を読み込む。

各エントリを 1〜10 点でスコアリング。以下の基準に従う:

**加点要素（バズりやすいパターン）:**
- 正解が一般的な思い込みと逆（「え？そうなの？」反応）: **+3点**
- 日本人に身近なテーマ（食べ物・動物・日常生活）: **+2点**
- 視覚的に表現しやすい（SD で背景画像を生成しやすい）: **+2点**
- 子供から大人まで誰でも楽しめる普遍的なテーマ: **+1点**
- difficulty が `easy`（簡単な問題ほど視聴者が「知らなかった！」と驚ける）: **+1点**

**減点要素:**
- ニッチすぎて日本人視聴者に馴染みがない（マイナー神話・地名など）: **-2点**
- `past_titles` と主題が重複または類似: **-10点**

最高スコアの1件を選定する。

### 3. Wikipedia からサムネイル画像 URL を取得

選定した質問のキーワード（`correct_answer` またはテーマの英語キーワード）を使って WebFetch ツールで以下を取得:
```
https://en.wikipedia.org/api/rest_v1/page/summary/{KEYWORD}
```

レスポンスの `thumbnail.source` を `image_url` として使用する。取得できない場合は空文字列。

### 4. 日本語コンテンツを生成

以下の点に注意して生成する:
- `japanese_title`: 「実は〇〇だった！」「〇〇の意外な真実」「知らなかった〇〇の秘密」などのフック形式（30文字以内）
- `japanese_summary`: 質問と答えを含む200-300文字の日本語説明。なぜ驚くべきかを強調する
- `key_points`: 3〜4件、40文字以内。「思い込み → 真実 → なぜそうなのか」の流れで構成
- `related_research`: WebSearch で補足情報を1〜2件検索（驚きのファクトを追加）

### 5. `02_selected.json` に保存

Write ツールで `.cache/pipeline/{run_id}/02_selected.json` に以下のスキーマで保存:

```json
{
  "title": "英語の質問文",
  "url": "opentdb://xxxxxxxx",
  "source": "opentdb",
  "image_url": "Wikipedia サムネイル URL または空文字",
  "japanese_title": "日本語タイトル（30文字以内）",
  "japanese_summary": "200-300文字の日本語要約",
  "interest_score": 8.5,
  "key_points": [
    "ポイント1（40文字以内）",
    "ポイント2（40文字以内）",
    "ポイント3（40文字以内）"
  ],
  "related_research": "WebSearch で得た補足情報"
}
```

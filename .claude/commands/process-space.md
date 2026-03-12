# /process-space

宇宙コンテンツから最も動画映えする1件を選定し、日本語コンテンツを生成して `02_selected.json` に保存する。

## 手順

### 1. 過去採用タイトルを取得（ネタ被り防止）

```bash
ls .cache/pipeline/*/02_selected.json 2>/dev/null
```

現在の `{run_id}` 以外のファイルを Read ツールで読み込み、`title` と `japanese_title` を `past_titles` リストとして収集する。ファイルがなければ `past_titles = []`。

### 2. 宇宙コンテンツをスコアリングして最良の1件を選定

Read ツールで `.cache/pipeline/{run_id}/01_space.json` を読み込む。

各エントリを 1〜10 点でスコアリング。以下の基準に従う:

**加点要素（バズりやすいパターン）:**
- 美しい画像が添付されている（APOD は基本的に高品質）: **+3点**
- 初めての発見・記録（「史上初」「最遠」「最大」など）: **+2点**
- スケールの大きさや宇宙の神秘を感じさせる内容: **+2点**
- JAXA・日本人宇宙飛行士が関係する内容: **+2点**
- 視聴者が「宇宙ってすごい！」と感じられる内容: **+1点**
- source が `nasa_apod`（高品質画像確定）: **+1点**

**減点要素:**
- 専門的すぎて一般人に難しい（粒子物理・高度な数式など）: **-2点**
- `past_titles` と主題が重複または類似: **-10点**

最高スコアの1件を選定する。

### 3. 日本語コンテンツを生成

以下の点に注意して生成する:
- `japanese_title`: 「NASAが撮影した〇〇の真の姿」「〇〇光年先に〇〇を発見」「〇〇が地球に接近中」などの壮大な形式（30文字以内）
- `japanese_summary`: 200-300文字の日本語説明。スケール感と発見の意義を強調する
- `key_points`: 3〜4件、40文字以内。「何が起きたか → なぜ特別か → スケール感」の流れで構成
- `related_research`: WebSearch で補足情報を1〜2件検索（関連する宇宙の事実を追加）

### 4. `02_selected.json` に保存

Write ツールで `.cache/pipeline/{run_id}/02_selected.json` に以下のスキーマで保存:

```json
{
  "title": "英語の元タイトル",
  "url": "https://apod.nasa.gov/... など",
  "source": "nasa_apod または nasa_rss",
  "image_url": "NASA 高品質画像 URL（APOD の場合は確実に存在）",
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

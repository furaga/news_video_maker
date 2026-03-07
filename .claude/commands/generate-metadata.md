# /gen-metadata

YouTube投稿用のメタデータ（説明文・タグ）を生成する。

## 手順

Read ツールで以下を読み込む:
- `.cache/pipeline/02_selected.json`
- `.cache/pipeline/03_script.json`

読み込んだ内容をもとに以下を生成する。

**説明文（`description`）** - 合計500文字以内:
- 1行目: 記事の核心を端的に表す文（50文字以内）← YouTube検索結果・通知に表示される部分
- 2〜4行目: `key_points` の内容を「・」箇条書きで展開（空の場合はスキップ）
- 5行目: `related_research` から最も興味深い補足情報を1文（空の場合はスキップ）
- 末尾固定テキスト:
  ```
  元記事: {source_url}

  ---
  このチャンネルでは海外テックニュースを日本語で毎日お届けします。

  #テックニュース #テクノロジー #ShortNews #Shorts
  ```

**タグ（`tags`）** - 15〜20個、各30文字以内:
- 記事固有タグ: 記事に登場する企業名・製品名・技術名を日本語と英語の両方（例: `Firefox`, `ファイアフォックス`）
- トピックタグ: 記事カテゴリに関する検索されやすい語（例: `セキュリティ`, `AI開発`）
- 定番タグ: `tech news`, `テックニュース`, `テクノロジー`, `ShortNews`, `Shorts`, `{source}`

生成後、Write ツールで `.cache/pipeline/05_metadata.json` に保存:

```json
{
  "description": "生成した説明文",
  "tags": ["タグ1", "タグ2", "..."],
  "generated_at": "YYYY-MM-DDTHH:MM:SS"
}
```

JSONが正しく生成できない場合は最大1回再試行する。

生成完了後、説明文とタグの内容を表示して確認を促す。

## 前提条件

- `.cache/pipeline/02_selected.json` が存在すること
- `.cache/pipeline/03_script.json` が存在すること

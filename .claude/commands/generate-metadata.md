# /gen-metadata

YouTube投稿用のメタデータ（説明文・タグ）を生成する。

## 手順

Read ツールで以下を読み込む:
- `.cache/pipeline/02_selected.json`
- `.cache/pipeline/03_script.json`

読み込んだ内容をもとに以下を生成する。

**タグ（`tags`）** - 15〜20個、各30文字以内:
- 記事固有タグ: 記事に登場する企業名・製品名・技術名を日本語と英語の両方（例: `Firefox`, `ファイアフォックス`）
- トピックタグ: 記事カテゴリに関する検索されやすい語（例: `セキュリティ`, `AI開発`）
- 定番タグ: `tech news`, `テックニュース`, `テクノロジー`, `AI`, `人工知能`, `ShortNews`, `Shorts`, `テック`, `{source}`

**説明文（`description`）**:
以下のフォーマットで生成する（タグは上で生成した `tags` 配列の全要素を `#` 付きで並べる）:

```
元記事: {source_url}

---
このチャンネルでは海外テックニュースを日本語で毎日お届けします。

#テックニュース #テクノロジー #AI #ShortNews #Shorts #{記事固有タグ1} #{記事固有タグ2} ...
```

- `元記事:` の行は必ず先頭に置く
- ハッシュタグ行は `#テックニュース #テクノロジー #AI #ShortNews #Shorts` を固定先頭に置き、続けて `tags` の記事固有タグを `#` 付きで並べる
- 記事の要約や箇条書きは含めない

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

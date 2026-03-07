# /gen-script

`.cache/pipeline/02_selected.json` の処理済み記事から、30〜60秒の日本語ナレーション動画用の台本を生成して `.cache/pipeline/03_script.json` に保存する。

## 手順

1. Read ツールで `.cache/pipeline/02_selected.json` を読み込む

2. 以下の構成で台本を生成:

   | セクション | 目的 | 目標尺 |
   |---|---|---|
   | `hook` | 視聴者の興味を引く導入 | 5秒（約35〜40文字） |
   | `main` | ニュース内容・意義を解説 | 20〜45秒（約140〜360文字） |
   | `outro` | まとめ・締め | 5〜10秒（約35〜80文字） |

3. 文字数から尺を推定（約7〜8文字/秒）し、合計が25〜60秒に収まるよう調整する
   - 60秒超 → `main` セクションを短縮して再生成（1回まで）
   - 25秒未満 → `main` セクションに情報を補足して再生成（1回まで）

4. Write ツールで `.cache/pipeline/03_script.json` に以下のスキーマで保存:

```json
{
  "title": "動画タイトル（60文字以内、#テックニュース #ShortNews を末尾に）",
  "source_url": "https://...",
  "image_url": "https://... (02_selected.json の image_url をそのまま引き継ぐ。なければ空文字)",
  "total_duration_sec": 45.0,
  "sections": [
    {
      "type": "hook",
      "narration_text": "VOICEVOX で読み上げるナレーション本文",
      "subtitle_text": "画面表示用の短縮テキスト（25文字以内）",
      "estimated_duration_sec": 5.0
    },
    {
      "type": "main",
      "narration_text": "...",
      "subtitle_text": "...",
      "estimated_duration_sec": 35.0
    },
    {
      "type": "outro",
      "narration_text": "...",
      "subtitle_text": "...",
      "estimated_duration_sec": 5.0
    }
  ]
}
```

## 品質基準

- 自然な日本語の話し言葉（「〜です」「〜ます」調）
- 専門用語は分かりやすく言い換えるか括弧で補足
- `subtitle_text` は `narration_text` の要点のみ（25文字以内目安）

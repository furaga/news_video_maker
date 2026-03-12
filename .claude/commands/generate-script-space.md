# /gen-script-space

`.cache/pipeline/02_selected.json` の宇宙コンテンツから、30〜60秒の日本語ナレーション動画用の台本を生成して `.cache/pipeline/03_script.json` に保存する。

## 手順

1. Read ツールで `.cache/pipeline/{run_id}/02_selected.json` を読み込む

2. 以下の **スケール→発見→感動** 構成で台本を生成:

   | セクション | 目的 | 目標尺 |
   |---|---|---|
   | `hook` | 宇宙のスケール感や驚きの事実で視聴者を引き込む | 4〜5秒（約30〜40文字） |
   | `main_1` | 何が発見・観測されたか、何が起きたかを説明 | 7〜10秒（約50〜80文字） |
   | `main_2` | なぜそれが特別なのか、何が凄いのかを強調 | 7〜10秒（約50〜80文字） |
   | `main_3` | スケール感を身近なものと比較して実感させる | 7〜10秒（約50〜80文字） |
   | `outro` | 「宇宙の広さを感じますね」などの余韻を残す締め | 4〜5秒（約30〜40文字） |

   **重要**:
   - `hook` は「地球から〇〇光年先に…」「今日、〇〇が起きました」など、宇宙のスケールや新鮮さを最初から感じさせる
   - `main_3` では日常的なものと比較してスケール感を具体化する（例: 「地球を100万個並べても…」）
   - `outro` には「チャンネル登録」を含めないこと

3. 文字数から尺を推定（約7〜8文字/秒）し、合計が25〜60秒に収まるよう調整する

4. Write ツールで `.cache/pipeline/{run_id}/03_script.json` に以下のスキーマで保存:

```json
{
  "title": "動画タイトル本文（30文字以内）",
  "source_url": "https://... (02_selected.json の url をそのまま引き継ぐ)",
  "image_url": "https://... (02_selected.json の image_url をそのまま引き継ぐ。なければ空文字)",
  "total_duration_sec": 40.0,
  "sections": [
    {
      "type": "hook",
      "narration_text": "VOICEVOX で読み上げるナレーション本文（カタカナ読み・ひらがな誤読防止）",
      "display_text": "画面字幕表示用（原語表記 + **キーワード** マークアップ）",
      "subtitle_text": "要点のみ（25文字以内）",
      "bg_prompt": "具体的な宇宙シーンを英語で記述したSD用プロンプト（下記ガイドライン参照）",
      "annotations": {},
      "estimated_duration_sec": 5.0
    },
    {
      "type": "main_1",
      "narration_text": "...",
      "display_text": "...",
      "subtitle_text": "...",
      "bg_prompt": "...",
      "annotations": {},
      "estimated_duration_sec": 9.0
    },
    {
      "type": "main_2",
      "narration_text": "...",
      "display_text": "...",
      "subtitle_text": "...",
      "bg_prompt": "...",
      "annotations": {},
      "estimated_duration_sec": 9.0
    },
    {
      "type": "main_3",
      "narration_text": "...",
      "display_text": "...",
      "subtitle_text": "...",
      "bg_prompt": "...",
      "annotations": {},
      "estimated_duration_sec": 9.0
    },
    {
      "type": "outro",
      "narration_text": "締めのナレーション（「チャンネル登録」は含めない）",
      "display_text": "...",
      "subtitle_text": "...",
      "bg_prompt": "...",
      "annotations": {},
      "estimated_duration_sec": 5.0
    }
  ]
}
```

### タイトル生成ガイドライン

YouTubeショートで伸びやすい壮大・驚き型タイトルを生成すること。

**フォーマット例（30文字以内の本文）:**
- `NASAが撮影した〇〇の真の姿` → 公式画像の権威性
- `〇〇光年先に〇〇を発見！` → スケール感
- `〇〇が地球に接近中` → 緊迫感
- `史上初！〇〇を観測` → 記録・歴史性
- `〇〇の大きさが想像を超えてた` → スケール感

**タイトルのキーワードマークアップ:**
- `title` フィールドにも `**keyword**` マークアップで強調したい単語を1〜2個指定する
- 宇宙の物体名・数字・「史上初」などを優先してマークアップする
- 例: `"**NASA**が撮影した〇〇の真の姿"`、`"**1億光年**先に〇〇を発見"`

### bg_prompt ガイドライン

各セクションの `bg_prompt` に、実際のコンテンツ（APOD の画像内容、発見内容）を反映した **Stable Diffusion 向け英語プロンプト** を生成する。

**ルール:**
- APODの場合、実際の天体・宇宙現象を具体的に描写する（例: `colorful nebula with pink and blue gas clouds, deep space, stars`）
- 宇宙撮影の雰囲気を出すキーワードを含める
- 末尾に必ず `photorealistic, 8k, cinematic, no text, no people` を追加する
- 具体的なシーン描写の例:
  - 「銀河」→ `spiral galaxy with glowing core, deep space, nebula`
  - 「惑星」→ `planet surface close-up, craters, colorful atmosphere`
  - 「超新星」→ `supernova explosion, bright light burst, deep space`
  - 「ブラックホール」→ `black hole with accretion disk, glowing orange ring, space`
  - 「星雲」→ `colorful nebula, gas and dust clouds, blue and purple tones, stars`
  - 「宇宙船・探査機」→ `spacecraft in orbit, Earth in background, solar panels`

### 品質基準

- 詩的・壮大な語り口（「〜です」「〜ます」調だが感動を込めて）
- 専門用語は分かりやすく言い換えるか括弧で補足
- `subtitle_text` は `narration_text` の要点のみ（25文字以内目安）
- `narration_text` に含まれるアルファベット・固有名詞は例外なくカタカナ読みで記述する
  （NASA → ナサ、APOD → エーポッド、Webb → ウェッブ、Hubble → ハッブル）
- VOICEVOXが誤読しやすい漢字はひらがなで記述する
- `display_text` では `narration_text` のカタカナ読みを元の表記に戻す（NASA、Webb 等）
- 視聴者に強調したいキーワードを `**keyword**` でマークアップ（1セクション2〜3個以内）

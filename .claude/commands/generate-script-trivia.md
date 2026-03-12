# /gen-script-trivia

`.cache/pipeline/02_selected.json` の雑学データから、30〜60秒の日本語ナレーション動画用の台本を生成して `.cache/pipeline/03_script.json` に保存する。

## 手順

1. Read ツールで `.cache/pipeline/{run_id}/02_selected.json` を読み込む

2. 以下の **クイズ→驚き→解説** 構成で台本を生成:

   | セクション | 目的 | 目標尺 |
   |---|---|---|
   | `hook` | 「〇〇って知ってる？」クイズ形式の問いかけ | 4〜5秒（約30〜40文字） |
   | `main_1` | よくある思い込みや誤解を提示 | 7〜10秒（約50〜80文字） |
   | `main_2` | 「実は…」の驚きの正解を明かす | 7〜10秒（約50〜80文字） |
   | `main_3` | なぜその答えになるのか背景・理由を解説 | 7〜10秒（約50〜80文字） |
   | `outro` | 「もう一つ知識が増えましたね」などの締め | 4〜5秒（約30〜40文字） |

   **重要**:
   - `hook` は視聴者が思わず止まってしまうような「え？知ってる？」形式の問いかけにする
   - `main_2` が最も重要なセクション。「実は〇〇なんです！」という驚きの瞬間を最大化する
   - `outro` には「チャンネル登録」を含めないこと

3. 文字数から尺を推定（約7〜8文字/秒）し、合計が25〜60秒に収まるよう調整する

4. Write ツールで `.cache/pipeline/{run_id}/03_script.json` に以下のスキーマで保存:

```json
{
  "title": "動画タイトル本文（30文字以内）",
  "source_url": "opentdb://... (02_selected.json の url をそのまま引き継ぐ)",
  "image_url": "https://... (02_selected.json の image_url をそのまま引き継ぐ。なければ空文字)",
  "total_duration_sec": 40.0,
  "sections": [
    {
      "type": "hook",
      "narration_text": "VOICEVOX で読み上げるナレーション本文（カタカナ読み・ひらがな誤読防止）",
      "display_text": "画面字幕表示用（原語表記 + **キーワード** マークアップ）",
      "subtitle_text": "要点のみ（25文字以内）",
      "bg_prompt": "具体的な物体・場所を英語で記述したSD用プロンプト（下記ガイドライン参照）",
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

YouTubeショートで伸びやすいフック型タイトルを生成すること。

**フォーマット例（30文字以内の本文）:**
- `実は〇〇だった！知らなかった…` → 驚き・後悔
- `〇〇の意外な真実` → 意外性
- `知ってた？〇〇の秘密` → クイズ形式
- `常識を覆す〇〇の真実` → 逆説
- `〇〇が実は〇〇だった件` → 口語的

**タイトルのキーワードマークアップ:**
- `title` フィールドにも `**keyword**` マークアップで強調したい単語を1〜2個指定する
- 驚きのポイントや主題キーワードを優先してマークアップする
- 例: `"**血液型**の意外な真実"`、`"実は**ガラス**は液体だった"`

### bg_prompt ガイドライン

各セクションの `bg_prompt` に、そのセリフの内容を視覚的に表現する **Stable Diffusion 向け英語プロンプト** を生成する。

**ルール:**
- 雑学の主題を具体的な物体・場所として描写する（例: `blood cells flowing in veins, microscopic view`）
- 照明・アングルを指定する（例: `soft lighting, macro photography`）
- 末尾に必ず `photorealistic, 8k, cinematic, no text, no people` を追加する
- 抽象的な概念は視覚的オブジェクトに変換する:
  - 「血液型」→ `blood drop on white background, microscope`
  - 「ガラス」→ `glass crystal close-up, refracting light`
  - 「動物の習性」→ `animal in natural habitat, wildlife photography`
  - 「歴史的事実」→ `ancient artifacts, historical objects, museum`

### 品質基準

- 自然な日本語の話し言葉（「〜です」「〜ます」調）
- 専門用語は分かりやすく言い換えるか括弧で補足
- `subtitle_text` は `narration_text` の要点のみ（25文字以内目安）
- `narration_text` に含まれるアルファベット・固有名詞は例外なくカタカナ読みで記述する
- VOICEVOXが誤読しやすい漢字はひらがなで記述する
- `display_text` では `narration_text` のカタカナ読みを元の表記に戻す（DJI、Google 等）
- 視聴者に強調したいキーワードを `**keyword**` でマークアップ（1セクション2〜3個以内）

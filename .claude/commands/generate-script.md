# /gen-script

`.cache/pipeline/02_selected.json` の処理済み記事から、30〜60秒の日本語ナレーション動画用の台本を生成して `.cache/pipeline/03_script.json` に保存する。

## 手順

1. Read ツールで `.cache/pipeline/02_selected.json` を読み込む

2. 以下の構成で台本を生成:

   | セクション | 目的 | 目標尺 |
   |---|---|---|
   | `hook` | 視聴者が次を見たくなる掴み（下記テクニック必須） | 3〜4秒（約20〜30文字） |
   | `main_1` | ニュースの概要・背景 | 7〜10秒（約50〜80文字） |
   | `main_2` | 詳細・技術的内容 | 7〜10秒（約50〜80文字） |
   | `main_3` | 関連情報・業界への影響 | 7〜10秒（約50〜80文字） |
   | `main_4` | 補足・今後の展望（**省略推奨。追加すると動画が長くなるため、情報量が十分あるときのみ使用**） | 7〜10秒（約50〜80文字） |
   | `outro` | まとめ | 4〜5秒（約30〜40文字） |

   **重要**:
   - セクションを細かく分けることで、各セクション切り替え時にカードアニメーションが発生し、画面に動きが生まれる。
   - `02_selected.json` に `related_research` フィールドがあれば、その情報を `main_3` や `main_4` に積極的に活用すること。
   - `outro` には「チャンネル登録」を含めないこと（動画終端のCTAセクションで自動追加される）。

### hook テクニック（必須）

hook の `narration_text` は以下の4パターンのいずれかで書くこと。**「〇〇が発表されました」のような平叙文は禁止。**

| パターン | 特徴 | 例 |
|---|---|---|
| **数字型** | 具体的な数字・記録で規模を即伝える | 「ジーピーユーたった2枚で、世界ランキング1位をとってしまいました。」 |
| **ひっくり返し型** | 意外な結末を1文で完結させる | 「アメリカの軍事ハッキングツールが、実はロシアのスパイに使われていました。」 |
| **緊迫感型** | 時間・速さ・喪失感で緊張感を出す | 「突然、世界中の開発者が使うサービスが、一夜で使えなくなりました。」 |
| **ループ型** | 最も驚くべき事実を冒頭に置き、疑問で締める | 「政府職員が国民数百万人のデータをUSBに詰めて持ち去っていた。なぜそんなことが起きたのか。」 |

（※「詳細はこのあと」「続きはこのあと」のような表現はショート動画に合わないため禁止）
（※セクション末尾に「しかし、一番驚くのはここからです。」のような引き文句を入れない。ナレーションは自然な流れで完結させること）

3. 文字数から尺を推定（約7〜8文字/秒）し、合計が25〜60秒に収まるよう調整する
   - 60秒超 → 各 `main_*` セクションを短縮して再生成（1回まで）
   - 25秒未満 → 各 `main_*` セクションに情報を補足して再生成（1回まで）

4. Write ツールで `.cache/pipeline/03_script.json` に以下のスキーマで保存（**すべてのフィールドは必須。特に `image_url`、`bg_prompt`、`display_text`、`annotations` を忘れないこと**）:

```json
{
  "title": "動画タイトル本文（30文字以内）",
  "source_url": "https://...",
  "image_url": "https://... (02_selected.json の image_url をそのまま引き継ぐ。なければ空文字)",
  "total_duration_sec": 45.0,
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
      "annotations": {"DJI": "中国ドローンメーカー"},
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
      "narration_text": "まとめのナレーション（「チャンネル登録」は含めない）",
      "display_text": "...",
      "subtitle_text": "...",
      "bg_prompt": "...",
      "annotations": {},
      "estimated_duration_sec": 5.0
    }
  ]
}
```

### annotations ガイドライン

各セクションの `annotations` に、字幕中の専門用語・略称・固有名詞の簡潔な説明を記述する。

**ルール:**
- キーは `display_text` 内の `**keyword**` マークアップで囲まれた用語と一致させる
- 値は日本語で簡潔な説明（10文字以内目安）
- 略称の正式名称や、一般視聴者が知らない可能性がある専門用語のみ対象
- 一般的に知られている用語（PlayStation、Google、YouTube など）や一般的な日本語には不要
- 同じ用語が複数セクションに出る場合、初出セクションのみに付ける（2回目以降は空の `{}` でよい）

### bg_prompt ガイドライン

各セクションの `bg_prompt` に、そのセリフの内容を視覚的に表現する **Stable Diffusion 向け英語プロンプト** を生成する。

**ルール:**
- **構図（最重要）**: メインの被写体が画面の50%以上を占めるクローズアップ・中望遠で撮影すること。必ず `close-up shot` または `macro photography` を指定する
- 具体的な物体・場所・人工物を英語で記述する（例: `PS5 DualSense controller on wooden desk, close-up shot`）
- 照明・アングルを指定する（例: `soft ambient lighting, close-up, eye-level shot`）
- 末尾に必ず `photorealistic, 8k, cinematic, no text` を追加する
- 抽象的な概念（「脆弱性」「ハッキング」「報奨金」）は視覚的なオブジェクトに変換する:
  - 「セキュリティ脆弱性」→ `digital padlock with crack, close-up, glowing circuit board`
  - 「ハッキング」→ `computer screen with code, close-up, dark room`
  - 「報奨金」→ `stack of dollar bills, close-up, shallow depth of field`
  - 「ロボット掃除機」→ `robot vacuum cleaner on floor, close-up shot, eye-level`
- 日本語キーワードをそのまま入れない（SD は日本語が苦手）
- **禁止**: 広い風景、パノラマ、俯瞰、都市遠景、skyline、aerial view は使わない。必ず具体的な被写体にフォーカスすること
  - BAD: `futuristic city skyline with glowing buildings, wide panoramic view`
  - GOOD: `smartphone screen showing AI chatbot interface, close-up, soft desk lamp lighting`
- **人物の活用（推奨）**: 人物を含めると視覚的インパクトが高まる。ただし顔のクローズアップは避け、後ろ姿・手元・シルエットなど部分的な描写を推奨する（SDの人体描画品質の制約のため）
  - GOOD: `technician's gloved hands pulling cable from server, close-up shot`
  - GOOD: `silhouette of person standing before wall of monitors, close-up shot`
  - BAD: `portrait of engineer smiling at camera`

## タイトル生成ガイドライン

YouTubeショートで伸びやすいフック型タイトルを生成すること。

**フォーマット例（30文字以内の本文）:**
- `〇〇がヤバいAIを発表` → 具体的な企業名＋驚き
- `〇〇がAI戦争に参戦` → 競争・対立構造
- `〇〇の新AIが常識を変える` → インパクト訴求
- `〇〇がついに〇〇を実現` → 期待・達成感
- `エンジニア必見！〇〇の新機能` → ターゲット訴求

**避けるべきタイトル:**
- 説明的すぎるタイトル（例: 「〇〇社が新しい〇〇機能を発表しました」）
- **30文字超えるタイトル本文**（YouTube Shorts 画面上部に表示するため短くすること）

**タイトルのキーワードマークアップ:**
- `title` フィールドにも `**keyword**` マークアップで強調したい単語を1〜2個指定する
- 企業名・製品名など固有名詞を優先してマークアップする（動画上で黄色テキストとして強調表示される）
- 例: `"**OpenAI**幹部が抗議辞任"`、`"**Apple**が新AIを発表"`
- `**...**` マークアップは動画の画面上タイトル表示（黄色強調）専用。YouTubeへのアップロード時は自動的に除去される。

## 品質基準

- 自然な日本語の話し言葉（「〜です」「〜ます」調）
- 専門用語は分かりやすく言い換えるか括弧で補足
- `subtitle_text` は `narration_text` の要点のみ（25文字以内目安）
- `narration_text` に含まれるアルファベット・固有名詞は例外なくカタカナ読みで記述する
  （例: API → エーピーアイ、URL → ユーアールエル、AI → エーアイ、
       GPU → ジーピーユー、iOS → アイオーエス、GitHub → ギットハブ、
       Google → グーグル、YouTube → ユーチューブ、Amazon → アマゾン、
       **OpenAI → オープンエーアイ**、Meta → メタ、Microsoft → マイクロソフト）
- VOICEVOXがアルファベットを正しく読めるか保証できないため、原則すべてカタカナ変換する
- `narration_text` では、VOICEVOXが誤読しやすい漢字はひらがなで記述する
  - 読みが複数ある漢字（多音字）は文脈に応じた正しい読みのひらがなに置換する
  （例: 「行っている」→「おこなっている」（実施の意味）/ 「いっている」（移動の意味）、
       「下さい」→「ください」、「上手い」→「うまい」、「今日」→「きょう」）

### display_text ガイドライン

`display_text` は画面上の字幕として表示されるテキスト。以下のルールで生成する:

- `narration_text` と同じ意味・構成だが、カタカナ読みを元の表記に戻す
  （例: ディージェーアイ → DJI、プレイステーション → PlayStation、グーグル → Google）
- 視聴者に強調したいキーワード（固有名詞・数字・驚きのポイント）を `**keyword**` でマークアップする
  （例: `**DJI**の掃除機を**PlayStation**のコントローラーで操作中に…`）
- 1セクション内の `**keyword**` は2〜3個以内にとどめる（強調しすぎない）
- 漢字の読み仮名（ひらがな化）は不要（表示用なので読みやすい漢字でよい）
- `narration_text` との文字数差は ±20% 以内に収める（尺の推定に影響するため）

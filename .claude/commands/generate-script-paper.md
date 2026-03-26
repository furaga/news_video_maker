# /gen-script-paper

`.cache/pipeline/02_selected.json` の処理済み論文から、30〜60秒の日本語ナレーション動画用の台本を生成して `.cache/pipeline/03_script.json` に保存する。

## 手順

1. Read ツールで `.cache/pipeline/02_selected.json` を読み込む

2. 以下の構成で台本を生成:

   | セクション | 目的 | 目標尺 |
   |---|---|---|
   | `hook` | 視聴者が次を見たくなる掴み（下記テクニック必須） | 3〜4秒（約20〜30文字） |
   | `main_1` | 研究の問い・既存の問題点（なぜこの研究が必要か） | 7〜10秒（約50〜80文字） |
   | `main_2` | 提案手法（何をどう解決したか、アイデアの核心） | 7〜10秒（約50〜80文字） |
   | `main_3` | 実験結果・性能向上の数値（従来比〇〇倍など） | 7〜10秒（約50〜80文字） |
   | `main_4` | 実用面のインパクト・今後の展望（任意） | 7〜10秒（約50〜80文字） |
   | `outro` | まとめ | 4〜5秒（約30〜40文字） |

   **重要**:
   - セクションを細かく分けることで、各セクション切り替え時にカードアニメーションが発生し、画面に動きが生まれる。
   - `02_selected.json` に `related_research` フィールドがあれば、その情報を `main_3` や `main_4` に積極的に活用すること。
   - `outro` には「チャンネル登録」を含めないこと（動画終端のCTAセクションで自動追加される）。

### hook テクニック（必須）

hook の `narration_text` は以下の4パターンのいずれかで書くこと。**「〇〇が提案されました」のような平叙文は禁止。**

| パターン | 特徴 | 例 |
|---|---|---|
| **数字型** | 具体的な数値改善で規模を即伝える | 「ジーピーユーたった2枚で、エーアイ世界ランキング1位をとってしまいました。」 |
| **ひっくり返し型** | 常識を覆す結果を1文で完結させる | 「モデルの重みを一切変えずに、性能を17パーセント以上あげることができました。」 |
| **緊迫感型** | 既存手法の限界を強調して問題意識を煽る | 「いまのエーアイには、〇〇という致命的な弱点があります。」 |
| **ループ型** | 最も驚くべき結果を冒頭に置き、疑問で締める | 「ジーピーユー2枚で世界1位をとった個人開発者がいます。その方法とは。」 |

**カリオシティーギャップ（好奇心の隙間）:** hook の最終文は、視聴者が「で、どうやって？」「なぜ？」と感じる形で終わらせる。以下のパターンから選ぶ:
- 疑問提示型: 「その方法とは。」「一体どんな仕組みなのか。」
- 逆説提示型: 「しかし、そのアイデアは全く常識外でした。」
- 規模強調型: 「一番驚くのはここからです。」

（※「詳細はこのあと」「続きはこのあと」のような表現はショート動画に合わないため禁止）

### セクション間ブリッジ（推奨）

`main_1` ～ `main_3` の `narration_text` 末尾に、次セクションへの引きとなる1文を加える。

- 例: 「では、その手法の核心とは何か。」
- 例: 「しかし、一番驚くのはここからです。」
- 例: 「実際の性能向上はどれほどだったのか、数字で見てみましょう。」

3. 文字数から尺を推定（約7〜8文字/秒）し、合計が25〜60秒に収まるよう調整する
   - 60秒超 → 各 `main_*` セクションを短縮して再生成（1回まで）
   - 25秒未満 → 各 `main_*` セクションに情報を補足して再生成（1回まで）

4. **BGM選定**: 台本の雰囲気に合う BGM を日本の無料 BGM サイトから検索して選ぶ。

   a. 台本全体の雰囲気を一言で表す（例: 明るい技術革新 / 緊張感のあるリスク / 落ち着いた学術）
   b. WebSearch ツールで合う BGM を検索する:
      - 検索例: `DOVA-SYNDROME BGM {雰囲気キーワード} site:dova-s.jp`
      - または: `魔王魂 BGM {雰囲気キーワード} site:maou.audio`
   c. WebFetch でトラックページを開き、直接 MP3 ダウンロード URL を取得する
   d. BGM が見つからない場合は `bgm_url: ""` を設定する（BGM なしで続行）

5. Write ツールで `.cache/pipeline/03_script.json` に以下のスキーマで保存（**すべてのフィールドは必須。特に `image_url`、`bg_prompt`、`display_text`、`annotations`、`bgm_url` を忘れないこと**）:

```json
{
  "title": "動画タイトル本文（30文字以内）",
  "source_url": "https://arxiv.org/abs/...",
  "image_url": "",
  "bgm_url": "https://.../*.mp3 (BGMの直接ダウンロードURL。見つからない場合は空文字)",
  "bgm_title": "BGMトラック名",
  "bgm_source_page": "https://... (BGMの参照元ページURL。なければ空文字)",
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
      "annotations": {"LLM": "大規模言語モデル"},
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
- 一般的に知られている用語（AI、Google、YouTube など）や一般的な日本語には不要
- 同じ用語が複数セクションに出る場合、初出セクションのみに付ける（2回目以降は空の `{}` でよい）

### bg_prompt ガイドライン

各セクションの `bg_prompt` に、そのセリフの内容を視覚的に表現する **Stable Diffusion 向け英語プロンプト** を生成する。

**ルール:**
- 具体的な物体・場所・人工物を英語で記述する（例: `glowing neural network visualization, multiple layers of nodes, blue light`）
- 照明・アングルを指定する（例: `soft ambient lighting, close-up, eye-level shot`）
- 末尾に必ず `photorealistic, 8k, cinematic, no text, no people` を追加する
- 抽象的な概念は視覚的なオブジェクトに変換する:
  - 「推論高速化」→ `fast flowing data streams, server rack with glowing blue lights`
  - 「精度向上」→ `target with bullseye, precision instruments, measurement tools`
  - 「学習・訓練」→ `computer screen showing training curves, neural network diagram`
  - 「ロボット制御」→ `robotic arm on laboratory table, mechanical joints, sensors`
  - 「自然言語処理」→ `text floating in digital space, word clouds, code on screen`
- 日本語キーワードをそのまま入れない（SD は日本語が苦手）

## タイトル生成ガイドライン

YouTubeショートで伸びやすい論文向けフック型タイトルを生成すること。

**フォーマット例（30文字以内の本文）:**
- `「**LLM**の推論が27倍速くなる」` → 数値インパクト
- `「**画像生成**の精度がついに人間超え」` → 達成感
- `「**ロボット**が道具を自分で作れるように」` → 驚き・意外性
- `「**強化学習**なしで自律飛行を実現」` → 手法の革新性
- `「エンジニア必見！**拡散モデル**の新手法」` → ターゲット訴求

**避けるべきタイトル:**
- 論文タイトルの直訳（難解・長い）
- 説明的すぎるタイトル（「〇〇チームが〇〇という手法を提案しました」）
- **30文字超えるタイトル本文**

**タイトルのキーワードマークアップ:**
- `title` フィールドにも `**keyword**` マークアップで強調したい単語を1〜2個指定する
- 技術分野名・手法名など動画の核心となる用語を優先する
- `**...**` マークアップは動画の画面上タイトル表示（黄色強調）専用。YouTubeへのアップロード時は自動的に除去される。

## 品質基準

- 自然な日本語の話し言葉（「〜です」「〜ます」調）
- 専門用語は分かりやすく言い換えるか括弧で補足
- `subtitle_text` は `narration_text` の要点のみ（25文字以内目安）
- `narration_text` に含まれるアルファベット・固有名詞は例外なくカタカナ読みで記述する
  （例: API → エーピーアイ、LLM → エルエルエム、GPU → ジーピーユー、
       Transformer → トランスフォーマー、arXiv → アーカイブ、
       RLHF → アールエルエイチエフ、LoRA → ローラ）
- VOICEVOXがアルファベットを正しく読めるか保証できないため、原則すべてカタカナ変換する
- `narration_text` では、VOICEVOXが誤読しやすい漢字はひらがなで記述する

### display_text ガイドライン

`display_text` は画面上の字幕として表示されるテキスト。以下のルールで生成する:

- `narration_text` と同じ意味・構成だが、カタカナ読みを元の表記に戻す
  （例: トランスフォーマー → Transformer、アーカイブ → arXiv、ローラ → LoRA）
- 視聴者に強調したいキーワード（技術名・数値・驚きのポイント）を `**keyword**` でマークアップする
- 1セクション内の `**keyword**` は2〜3個以内にとどめる（強調しすぎない）
- 漢字の読み仮名（ひらがな化）は不要（表示用なので読みやすい漢字でよい）
- `narration_text` との文字数差は ±20% 以内に収める（尺の推定に影響するため）

# /gen-script-paper

`.cache/pipeline/02_selected.json` の処理済み論文から、30〜60秒の日本語ナレーション動画用の台本を生成して `.cache/pipeline/03_script.json` に保存する。

**共通ルール**: JSON スキーマの構造、annotations の付け方、bg_prompt の基本ルール（構図・禁止事項・人物の扱い）、display_text の作り方、カタカナ変換・誤読防止などの品質基準は `.claude/commands/generate-script.md` に準拠する。本ファイルには論文向けの差分のみ記載する。

## 手順

1. Read ツールで `.cache/pipeline/02_selected.json` を読み込む

2. 以下の構成で台本を生成（セクションの目的は news 版と異なる）:

   | セクション | 目的 | 目標尺 |
   |---|---|---|
   | `hook` | 視聴者が次を見たくなる掴み（下記テクニック必須） | 3〜4秒（約20〜30文字） |
   | `main_1` | 研究の問い・既存の問題点（なぜこの研究が必要か） | 7〜10秒（約50〜80文字） |
   | `main_2` | 提案手法（何をどう解決したか、アイデアの核心） | 7〜10秒（約50〜80文字） |
   | `main_3` | 実験結果・性能向上の数値（従来比〇〇倍など） | 7〜10秒（約50〜80文字） |
   | `main_4` | 実用面のインパクト・今後の展望（任意） | 7〜10秒（約50〜80文字） |
   | `outro` | まとめ | 4〜5秒（約30〜40文字） |

   セクション細分化の理由・`related_research` の活用・outro に「チャンネル登録」を含めない、は generate-script.md と同じ。

### hook テクニック（必須）

パターンの種類（数字型・ひっくり返し型・緊迫感型・ループ型）と平叙文禁止のルールは generate-script.md と共通。論文向けの例:

| パターン | 例 |
|---|---|
| 数字型 | 「ジーピーユーたった2枚で、エーアイ世界ランキング1位をとってしまいました。」 |
| ひっくり返し型 | 「モデルの重みを一切変えずに、性能を17パーセント以上あげることができました。」 |
| 緊迫感型 | 「いまのエーアイには、〇〇という致命的な弱点があります。」 |
| ループ型 | 「ジーピーユー2枚で世界1位をとった個人開発者がいます。その方法とは。」 |

**カリオシティーギャップ（論文向け追加ルール）**: hook の最終文は、視聴者が「で、どうやって？」「なぜ？」と感じる形で終わらせる。
- 疑問提示型: 「その方法とは。」「一体どんな仕組みなのか。」
- 逆説提示型: 「しかし、そのアイデアは全く常識外でした。」
- 規模強調型: 「一番驚くのはここからです。」

（※「詳細はこのあと」「続きはこのあと」のような表現はショート動画に合わないため禁止）

### セクション間ブリッジ（推奨、論文向け追加ルール）

`main_1`〜`main_3` の `narration_text` 末尾に、次セクションへの引きとなる1文を加える。
- 例: 「では、その手法の核心とは何か。」「しかし、一番驚くのはここからです。」「実際の性能向上はどれほどだったのか、数字で見てみましょう。」

3. 文字数から尺を推定（約7〜8文字/秒）し、合計が25〜60秒に収まるよう調整する（60秒超・25秒未満のときの再生成ルールは generate-script.md と同じ、1回まで）

4. Write ツールで `.cache/pipeline/03_script.json` に保存（フィールドの意味は generate-script.md 参照。**すべて必須**）:

```json
{
  "title": "動画タイトル本文（30文字以内）",
  "source_url": "https://arxiv.org/abs/...",
  "image_url": "",
  "total_duration_sec": 45.0,
  "sections": [
    { "type": "hook", "narration_text": "...", "display_text": "...", "subtitle_text": "...", "bg_prompt": "...", "annotations": {}, "estimated_duration_sec": 5.0 },
    { "type": "main_1", "narration_text": "...", "display_text": "...", "subtitle_text": "...", "bg_prompt": "...", "annotations": {"LLM": "大規模言語モデル"}, "estimated_duration_sec": 9.0 },
    { "type": "main_2", "narration_text": "...", "display_text": "...", "subtitle_text": "...", "bg_prompt": "...", "annotations": {}, "estimated_duration_sec": 9.0 },
    { "type": "main_3", "narration_text": "...", "display_text": "...", "subtitle_text": "...", "bg_prompt": "...", "annotations": {}, "estimated_duration_sec": 9.0 },
    { "type": "outro", "narration_text": "まとめのナレーション（「チャンネル登録」は含めない）", "display_text": "...", "subtitle_text": "...", "bg_prompt": "...", "annotations": {}, "estimated_duration_sec": 5.0 }
  ]
}
```

`image_url` は論文には記事画像がないため常に空文字。`source_url` は arXiv の URL。

### bg_prompt の抽象概念変換（論文向け）

構図・照明・禁止事項（広い風景やパノラマ禁止）・人物の扱いは generate-script.md の bg_prompt ガイドラインに準拠。論文特有の変換例:

- 「推論高速化」→ `server rack with glowing blue lights, close-up, shallow depth of field`
- 「精度向上」→ `target with bullseye, close-up, precision instruments`
- 「学習・訓練」→ `computer screen showing training curves, close-up, neural network diagram`
- 「ロボット制御」→ `robotic arm on laboratory table, close-up, mechanical joints`
- 「自然言語処理」→ `computer screen with code, close-up, soft glow`

## タイトル生成ガイドライン

YouTubeショートで伸びやすい論文向けフック型タイトルを生成する（news 版のような数字・大企業訴求ではなく、技術的インパクトそのものを主役にする）。

**フォーマット例（30文字以内の本文）:**
- `「**LLM**の推論が27倍速くなる」` → 数値インパクト
- `「**画像生成**の精度がついに人間超え」` → 達成感
- `「**ロボット**が道具を自分で作れるように」` → 驚き・意外性
- `「**強化学習**なしで自律飛行を実現」` → 手法の革新性
- `「エンジニア必見！**拡散モデル**の新手法」` → ターゲット訴求

**避けるべきタイトル:**
- 論文タイトルの直訳（難解・長い）
- 説明的すぎるタイトル（「〇〇チームが〇〇という手法を提案しました」）
- **30文字超のタイトル本文**

**タイトルのキーワードマークアップ**: generate-script.md と同じルール（`**keyword**` を1〜2個、アップロード時に自動除去）。技術分野名・手法名を優先してマークアップする。

## 品質基準

自然な話し言葉・カタカナ変換・誤読防止のひらがな化・display_text の作り方は generate-script.md の品質基準に準拠する。論文特有語彙のカタカナ変換を追加:

（例: LLM → エルエルエム、Transformer → トランスフォーマー、arXiv → アーカイブ、RLHF → アールエルエイチエフ、LoRA → ローラ）

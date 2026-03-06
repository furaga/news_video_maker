# 仕様書: 台本生成（Script Generator）

## 目的

処理済み記事から、30〜60秒の日本語ナレーション動画用の台本を生成する。処理は Claude Code（LLM）が担当する。

## 対応コマンド

`.claude/commands/generate-script.md` → `/gen-script`

## 担当

Claude Code（LLM処理）

---

## 入力

**ファイル**: `.cache/pipeline/02_selected.json`（`specs/02_content_processor.md` の出力）

---

## 出力

**ファイル**: `.cache/pipeline/03_script.json`

**スキーマ**（`VideoScript`）:

```json
{
  "title": "動画タイトル（YouTubeに投稿するタイトル、60文字以内）",
  "source_url": "https://...",
  "total_duration_sec": 45.0,
  "sections": [
    {
      "type": "hook",
      "narration_text": "ナレーション本文（VOICEVOX で読み上げるテキスト）",
      "subtitle_text": "画面に表示する字幕（短縮版）",
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

---

## データモデル

`src/news_video_maker/script/models.py`（実装時に追加）:

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class ScriptSection:
    type: Literal["hook", "main", "outro"]
    narration_text: str
    subtitle_text: str
    estimated_duration_sec: float

@dataclass
class VideoScript:
    title: str
    source_url: str
    total_duration_sec: float
    sections: list[ScriptSection]
```

---

## 振る舞い

### 台本の構成

| セクション | 目的 | 目標尺 |
|---|---|---|
| `hook` | 視聴者の興味を引く導入 | 5秒 |
| `main` | ニュースの内容・意義を解説 | 20〜45秒 |
| `outro` | まとめ・締め | 5〜10秒 |

### 尺の推定

VOICEVOX の日本語読み上げ速度を基準に推定:
- **標準速度**: 約 7〜8文字/秒
- 例: 35秒 → 約 245〜280 文字

### 台本の品質基準

- 自然な日本語の話し言葉（書き言葉ではなく）
- 「〜です」「〜ます」調で統一
- 専門用語は分かりやすく言い換え、または「〜と呼ばれる技術」などで補足
- `subtitle_text` は `narration_text` の要点のみ（25文字以内を目安）

### YouTube タイトルの生成

- `#テックニュース` `#ShortNews` などのハッシュタグを末尾に付ける
- 60文字以内

---

## エラー処理

- `total_duration_sec` が 60 秒を超える場合は `main` セクションを短縮して再生成する（1回まで）
- `total_duration_sec` が 25 秒未満の場合は `main` セクションに情報を補足して再生成する（1回まで）

---

## コマンド実装ノート（`.claude/commands/generate-script.md`）

1. `Read` ツールで `.cache/pipeline/02_selected.json` を読み込む
2. Claude 自身が台本を生成する
3. 文字数カウントで尺を推定し、必要に応じて調整する
4. `Write` ツールで `.cache/pipeline/03_script.json` を保存する

---

## テスト方針

コマンド実行による E2E テストで確認:

- 正常系: `02_selected.json` から `03_script.json` が生成されること
- `sections` に `hook`, `main`, `outro` の3種類が含まれること
- `total_duration_sec` が 25〜60 の範囲であること
- `subtitle_text` が各セクションで 25 文字以内であること（概ね）

# 仕様書: 動画生成（Video Generator）

## 目的

生成した台本から、VOICEVOX で音声合成し、Pillow で背景画像を生成、moviepy で組み合わせて MP4 動画を出力する。

## 対応コマンド

`.claude/commands/generate-video.md` → `/gen-video`

## 担当

Python（VOICEVOX + moviepy + Pillow）
コマンドは `src/news_video_maker/video/` の Python スクリプトを Bash ツールで呼び出す。

---

## 入力

**ファイル**: `.cache/pipeline/03_script.json`（`specs/03_script_generator.md` の出力）

---

## 出力

- **動画ファイル**: `output/<YYYYMMDD>_<HHMMSS>.mp4`
- **パスファイル**: `.cache/pipeline/04_video_path.txt`（動画ファイルの絶対パス）

---

## 動画仕様

| 項目 | 値 |
|---|---|
| 解像度 | 1080 × 1920 px（9:16 縦型、YouTube Shorts 対応） |
| フレームレート | 30 fps |
| 映像コーデック | H.264 |
| 音声コーデック | AAC |
| コンテナ | MP4 |

---

## 振る舞い

### ステップ1: 音声合成（VOICEVOX）

`src/news_video_maker/video/tts.py` が担当。

各セクションの `narration_text` を VOICEVOX HTTP API で音声合成する:

1. `POST http://localhost:50021/audio_query` でクエリ生成
   - `speaker`: 設定値（デフォルト: 3 = ずんだもん）
   - `text`: ナレーションテキスト
2. `POST http://localhost:50021/synthesis` で WAV 生成
3. 生成した WAV を `.cache/audio/<section_index>.wav` に保存

VOICEVOX の話者 ID は `config.py` で設定可能にする。

### ステップ2: 背景画像生成

`src/news_video_maker/video/background.py` と `src/news_video_maker/video/visuals.py` が担当。

背景画像の優先順位（`composer.py` で制御）:

1. `image_url` が指定されている場合: 記事画像をダウンロードして base64 化
2. `image_url` 未指定または取得失敗の場合: **ローカル拡散モデルでAI生成**（各セクションの `bg_prompt` を使用）
   - モデル: `SD_MODEL_ID`（デフォルト `Lykon/dreamshaper-xl-v2-turbo`）。`AutoPipelineForText2Image` で SD1.5/SDXL 両対応
   - **SDXL Turbo 系**（ID に `xl` を含む）: 832×704 生成 / 7 steps / cfg 2.0、`enable_model_cpu_offload()` + `vae.enable_slicing()`（8GB VRAM 対応・`.to("cuda")` は使わない）
   - **SD1.5 系**（従来）: 512×448 生成 / 30 steps / cfg 7.5 に自動で切替
   - スケジューラはモデル同梱設定を使用（Turbo 系は DPM++ SDE）
   - 生成後 PIL で `OUTPUT_SIZE`（1080×920）へリサイズし `.cache/images/<run_id>/bg_<i>.png` に保存
   - 初回のみモデルDL（SDXL Turbo は約7GB）。`diffusers` 未インストール時はスキップして次のフォールバックへ
3. AI生成も失敗した場合: 背景窓は空（クリーム地）のまま合成を継続する

#### 画面レイアウト（D3 クリーム版）

`visuals.py` の HTML/CSS テンプレート（`_SUBTITLE_TEMPLATE` / `_CTA_TEMPLATE`）で 1080×1920 を構成する。フォントは M PLUS 1p 900。

| 要素 | 仕様 |
|---|---|
| 全体背景 | クリーム `#F7F4EC` |
| タイトル部 | 上部 0〜520px のクリーム紙面（`padding: 150px 56px 0`）。下端に `3px double #1a1a1a` の二重罫線 |
| タイトル文字 | 黒 `#111` / 100px、キーワードは赤 `#C41E1E`（縁取りなし、`letter-spacing:-1px`） |
| 背景画像窓 | `top:520px` 〜 `bottom:480px` の帯（Ken Burns で拡大＋パン） |
| 字幕 | 下部 `bottom:230px`。ダークバンド `rgba(20,18,14,0.92)` + クリーム文字 `#F7F4EC` / 64px、キーワードは金 `#FFD25E` |
| ruby 注釈 | `rt { color:#cbb98a; background:transparent }`（ダークバンドと調和させる） |
| CTA（末尾） | 同トーン（クリーム背景 + ダークバンド文字 + 絵文字 👍🔔） |
| メタ情報 | カテゴリ・日付は表示しない |

#### Ken Burns 効果

`visuals.py` の Playwright レンダリング時に `.bg`（`#bg` 要素）のズーム・パンを時間経過で変化させる:

- セクション内ローカル進行で `scale 1.0 → 1.20`
- パン: `section_start` が偶数秒帯なら右・奇数秒帯なら左（`translate(±40px × progress, -15px × progress)`）
- 各フレームは moviepy の `VideoClip` にそのまま渡す（セクションごとの PNG 個別保存はしない）

### ステップ3: 動画合成（moviepy）

`src/news_video_maker/video/composer.py` が担当。

1. 各セクションの WAV の実際の長さを取得
2. PNG 画像から `ImageClip` を作成（duration = WAV の長さ）
3. `AudioFileClip` で WAV を読み込む
4. 各セクションのクリップを `CompositeVideoClip` で合成
5. セクションを `concatenate_videoclips` で結合
6. `write_videofile()` で MP4 出力
   - `codec="libx264"`, `audio_codec="aac"`, `fps=30`

### 字幕タイミング計算

字幕チャンクのタイミングは以下の方法で決定する（文字数比率は使用しない）:

1. `display_text` を 。！？ で文ごとに分割
2. `narration_text` を同じ区切りで分割（文数が一致していること前提）
3. 各 `narration_text` の文を VOICEVOX で個別合成し、実際の音声長を測定
4. 各文の音声長の比率でセクションの総尺を分配
5. 文内のサブチャンク（`**keyword**` 境界）は文字数比率で按分

この方式により、文字数では予測できない VOICEVOX の読み上げ速度の違いを正確に反映できる。
個別合成の WAV は `.cache/audio/sentences/` にキャッシュする。

**制約**: `narration_text` と `display_text` の文数（。！？ による区切り数）は一致していなければならない。

---

## モジュール構成

### `src/news_video_maker/video/tts.py`

```python
# VOICEVOX HTTP API クライアント
# 入力: テキスト, 話者ID
# 出力: WAV ファイルパス
def synthesize(text: str, speaker_id: int, output_path: Path) -> Path: ...
```

### `src/news_video_maker/video/visuals.py`

```python
# Pillow テキストカード生成
# 入力: subtitle_text, source_name, image_url（省略可）
# 出力: PNG ファイルパス
def generate_text_card(subtitle_text: str, source: str, output_path: Path, image_url: str | None = None) -> Path: ...
```

### `src/news_video_maker/video/composer.py`

```python
# moviepy 動画合成
# 入力: VideoScript（JSON から復元）
# 出力: MP4 ファイルパス
def compose_video(script: VideoScript, output_path: Path) -> Path: ...
```

---

## エラー処理

- **VOICEVOX 接続失敗**: `VOICEVOX_URL` への接続エラー時は詳細メッセージを表示し停止。「VOICEVOXが起動しているか確認してください」とガイドする
- **VOICEVOX API エラー**: リトライ 3 回（1秒待機）。それでも失敗したら停止
- **Pillow フォントが見つからない**: フォールバックとして `ImageFont.load_default()` を使用し警告を出す
- **moviepy レンダリング失敗**: 中間ファイル（WAV・PNG）は保持したままエラーログを出力

---

## 中間ファイル

成功時に以下のキャッシュは **削除しない**（デバッグ・再利用のため保持）:

```
.cache/
  audio/
    00_hook.wav
    01_main.wav
    02_outro.wav
  images/
    00_hook.png
    01_main.png
    02_outro.png
```

---

## 実装ノート

- VOICEVOX のエンドポイント: `POST /audio_query?text={text}&speaker={id}` → `POST /synthesis?speaker={id}`
- moviepy v2 では `concatenate_videoclips` の引数が v1 と異なる場合があるため、`use context7` で `moviepy` の最新 API を確認すること
- Pillow の `ImageDraw.textbbox()` でテキスト領域を計算してから中央配置する
- `output/` ディレクトリが存在しない場合は自動作成する

---

## テスト方針

- `tests/video/test_composer.py`
- VOICEVOX API 呼び出しはモック
- 実際の WAV ファイル（短い無音）を使った合成テストを最低1件用意
- 生成された MP4 の存在確認

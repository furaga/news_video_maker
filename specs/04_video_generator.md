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
2. `image_url` 未指定または取得失敗の場合: **Stable Diffusion（SD 1.5）でAI生成**
   - モデル: `runwayml/stable-diffusion-v1-5`（Hugging Face diffusers、ローカル・無料）
   - 生成サイズ: 576×1024（9:16）→ PIL で 1080×1920 にリサイズ
   - キャッシュ: `.cache/images/bg_generated.png`
   - 初回実行時のみモデルダウンロード（~4GB）
   - `diffusers` 未インストールの場合はスキップして次のフォールバックへ
3. AI生成も失敗した場合: 暗い青 CSS グラデーション（既存動作）

#### Ken Burns 効果

`visuals.py` の Playwright レンダリング時に `.bg` 要素のズームを時間経過で変化させる:

- 動画開始時: `transform: scale(1.06)`
- 動画終了時: `transform: scale(1.14)`
- 計算式: `scale = 1.06 + 0.08 * (globalTime / totalDuration)`
- `globalTime` = 動画全体での絶対時刻（セクション開始時刻 + セクション内経過時刻）
- テキスト: `subtitle_text` を中央寄せで表示
  - フォント: システムの日本語フォント（`C:/Windows/Fonts/meiryo.ttc` または `YuGothic`）
  - フォントサイズ: 72px
  - 色: 白
- ソース表記: 右下に「Source: {source}」を小さく表示（32px、グレー）
- 生成した PNG を `.cache/images/<section_index>.png` に保存

### ステップ3: 動画合成（moviepy）

`src/news_video_maker/video/composer.py` が担当。

1. 各セクションの WAV の実際の長さを取得
2. PNG 画像から `ImageClip` を作成（duration = WAV の長さ）
3. `AudioFileClip` で WAV を読み込む
4. 各セクションのクリップを `CompositeVideoClip` で合成
5. セクションを `concatenate_videoclips` で結合
6. `write_videofile()` で MP4 出力
   - `codec="libx264"`, `audio_codec="aac"`, `fps=30`

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

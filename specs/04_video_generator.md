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

### BGM 関連フィールド（`03_script.json` ルートレベル）

| フィールド | 型 | 説明 |
|---|---|---|
| `bgm_url` | `string` | BGM の直接ダウンロード URL（MP3/WAV）。空文字の場合は BGM なし |
| `bgm_title` | `string` | BGM トラック名（ログ・デバッグ用） |
| `bgm_source_page` | `string` | BGM の参照元ページ URL（クレジット表記用） |

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

### ステップ0: BGM ダウンロード（bgm_cache.py）

`src/news_video_maker/video/bgm_cache.py` が担当。

台本の `bgm_url` フィールドに直接ダウンロード URL が設定されている場合、初回のみダウンロードして `assets/bgm/cache/` にキャッシュする。

- キャッシュパス: `assets/bgm/cache/{sha256(url)[:16]}.mp3`（または .wav）
- キャッシュ済みの場合は再ダウンロードしない
- ダウンロード失敗時は None を返してパイプラインを停止しない（BGM なしで続行）
- `bgm_url` が空の場合は None を返す（後方互換）

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
3. 映像クリップのみ生成（音声は後でまとめてミックス）
4. セクションを `concatenate_videoclips` で結合
5. `audio_mixer.mix_audio()` で BGM・SFX・ナレーションを合成した音声を生成
6. `final.with_audio(mixed_audio)` で音声を映像に付与
7. `write_videofile()` で MP4 出力
   - `codec="libx264"`, `audio_codec="aac"`, `fps=30`

### ステップ3.5: 音声ミックス（audio_mixer.py）

`src/news_video_maker/video/audio_mixer.py` が担当。

以下の音声トラックを `CompositeAudioClip` で合成する:

1. **ナレーション**: 各セクションの WAV を開始時刻に配置（`with_start(t)`）
2. **BGM**: `bgm_path` が指定されている場合
   - 動画総尺より短い場合は `AudioLoop` でループ
   - 長い場合は `subclipped(0, total_duration)` でカット
   - `MultiplyVolume(BGM_VOLUME)` で音量調整（デフォルト: 0.18）
   - `AudioFadeIn(1.0)` + `AudioFadeOut(2.0)` でフェード
3. **SFX**: `assets/sfx/transition/` にファイルがある場合
   - `section_starts[1:]` のタイミング（最初のセクション以外の全切り替え点）に配置
   - `MultiplyVolume(SFX_VOLUME)` で音量調整（デフォルト: 0.5）
   - BGM/SFX フォルダが存在しない・空の場合はスキップ（後方互換）

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

### `src/news_video_maker/video/bgm_cache.py`

```python
# BGM URL からキャッシュパスを返す（初回のみダウンロード）
# 入力: bgm_url (str)
# 出力: キャッシュ済みファイルパス、または None（URL 空・失敗時）
def get_bgm_path(bgm_url: str) -> Path | None: ...
```

### `src/news_video_maker/video/audio_mixer.py`

```python
# ナレーション・BGM・SFX を CompositeAudioClip でミックス
# 入力: ナレーション WAV リスト、開始時刻リスト、総尺、BGM パス
# 出力: ミックス済み AudioClip
def mix_audio(
    narration_wavs: list[Path],
    section_starts: list[float],
    total_duration: float,
    bgm_path: Path | None = None,
    bgm_volume: float = BGM_VOLUME,
) -> AudioClip: ...
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

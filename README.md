# news_video_maker

海外テックニュース・論文を日本語ナレーション付きの YouTube Shorts に自動変換・投稿するツール。

## アーキテクチャ

```
scripts/run_pipeline.py (Claude Agent SDK)
  → Claude Code CLI
    → .claude/commands/ の各コマンドを順次実行
```

### ニュースモード（デフォルト）

| ステージ | コマンド | 処理内容 | 実装 |
|---|---|---|---|
| 1 | `/fetch-news` | RSS からニュース記事を取得 | Python (feedparser) |
| 2 | `/process` | 記事選定・日本語要約 | Claude LLM |
| 3 | `/gen-script` | ナレーション台本生成 | Claude LLM |
| 4 | `/gen-metadata` | YouTube メタデータ生成 | Claude LLM |
| 5 | `/gen-video` | 音声合成 + 動画生成 | Python (VOICEVOX + moviepy) |
| 6 | `/upload` | YouTube にアップロード | Python (YouTube Data API v3) |

### 論文モード（`--mode paper`）

| ステージ | コマンド | 処理内容 | 実装 |
|---|---|---|---|
| 1 | `/fetch-papers` | arXiv / HuggingFace Daily Papers から論文取得 | Python |
| 2 | `/process-paper` | 論文選定・日本語要約 | Claude LLM |
| 3 | `/gen-script-paper` | ナレーション台本生成 | Claude LLM |
| 4〜6 | 共通 | 動画生成・アップロード | 同上 |

ステージ間のデータは `.cache/pipeline/` 以下の JSON ファイルで受け渡す。

## セットアップ

### 前提条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [VOICEVOX](https://voicevox.hiroshiba.jp/)（ローカルで起動しておく、または自動起動）
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

### インストール

```bash
uv sync
```

### 環境変数

`.env.example` をコピーして `.env` を作成し、各キーを設定する。

```bash
cp .env.example .env
```

| 変数名 | 説明 |
|---|---|
| `YOUTUBE_CLIENT_SECRET_PATH` | OAuth 2.0 クライアントシークレットのパス |
| `YOUTUBE_PRIVACY` | 公開設定 (`public` / `unlisted` / `private`) |
| `CHANNEL_NAME` | チャンネル名 |
| `CHANNEL_HASHTAGS` | ハッシュタグ |
| `CHANNEL_DESCRIPTION_FOOTER` | 説明欄のフッター |
| `VOICEVOX_URL` | VOICEVOX エンジンの URL（デフォルト: `http://localhost:50021`） |
| `SD_MODEL_ID` | 背景画像生成モデル（デフォルト: `Lykon/dreamshaper-8`） |
| `VIDEO_BG_MODE` | `1` で AnimateDiff 背景動画モードを有効化 |

## 使い方

### パイプライン一括実行

```bash
# ニュースモード（デフォルト）
uv run python scripts/run_pipeline.py

# 論文モード
uv run python scripts/run_pipeline.py --mode paper

# YouTube 投稿をスキップ（動画生成まで）
uv run python scripts/run_pipeline.py --dry-run

# 翌日 08:00 JST に公開予約
uv run python scripts/run_pipeline.py --publish-time 8:00

# 途中ステージから再開（例: ステージ3 = 台本生成から）
uv run python scripts/run_pipeline.py --from-stage 3
```

### 定期スケジューラー

指定した時刻スロットに動画が予約済みかチェックし、不足分を自動生成・投稿する。

```bash
uv run python scripts/scheduler.py --config scheduler_config.yaml
```

### 個別ステージ実行（Claude Code コマンド）

Claude Code 内で各コマンドを個別に実行できる。

```
/fetch-news
/process
/gen-script
/gen-metadata
/gen-video
/validate-video
/review-video
/upload
```

## プロジェクト構成

```
src/news_video_maker/
  config.py             # 設定読み込み
  pipeline.py           # パイプライン制御
  history.py            # 投稿履歴管理
  fetcher/
    rss.py              # RSS フィード取得
    paper.py            # arXiv / HuggingFace 論文取得
    models.py           # データモデル
    post_comments.py    # YouTube コメント取得
  video/
    tts.py              # VOICEVOX 音声合成
    visuals.py          # Playwright + HTML/CSS による映像素材生成
    composer.py         # 動画合成
    background.py       # Stable Diffusion 背景画像生成
    validator.py        # 動画バリデーション
  uploader/
    youtube.py          # YouTube アップロード
scripts/
  run_pipeline.py       # パイプライン実行エントリーポイント
  scheduler.py          # 定期スケジューラー
specs/                  # 仕様書
.claude/commands/       # Claude Code カスタムコマンド
output/                 # 生成動画
.cache/                 # 中間ファイル（音声・画像・パイプラインデータ）
```

## 動画生成の仕組み

- **音声合成**: VOICEVOX（ローカル実行、高品質日本語 TTS）
- **映像**: Playwright + HTML/CSS でフレームをレンダリング → moviepy で合成
  - 字幕: 黄色テキスト＋黒縁取り（YouTube Shorts セーフゾーン準拠）
  - タイトル: 白テキスト＋左赤ボーダー
  - Ken Burns 効果（ズームイン＋左右パン）
- **背景画像**: Stable Diffusion（Lykon/dreamshaper-8）でセクション別に生成
  - `SD_MODEL_ID` 環境変数でモデル変更可能
  - diffusers 未インストール時は暗い青背景にフォールバック
- **背景動画モード**: `VIDEO_BG_MODE=1` で AnimateDiff v3 による動画背景を有効化

## 仕様書

各モジュールの詳細な仕様は `specs/` ディレクトリを参照。

## ライセンス

Private

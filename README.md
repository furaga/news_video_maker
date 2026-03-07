# news_video_maker

海外テックニュースを日本語ナレーション付きの YouTube Shorts に自動変換・投稿するツール。

## アーキテクチャ

```
scripts/run_pipeline.py (Claude Agent SDK)
  → Claude Code CLI
    → .claude/commands/ の各コマンドを順次実行
```

| ステージ | コマンド | 処理内容 | 実装 |
|---|---|---|---|
| 1 | `/fetch-news` | RSS からニュース記事を取得 | Python (feedparser) |
| 2 | `/process` | 記事選定・日本語要約 | Claude LLM |
| 3 | `/gen-script` | ナレーション台本生成 | Claude LLM |
| 4 | `/gen-metadata` | YouTube メタデータ生成 | Claude LLM |
| 5 | `/gen-video` | 音声合成 + 動画生成 | Python (VOICEVOX + moviepy) |
| 6 | `/upload` | YouTube にアップロード | Python (YouTube Data API v3) |

ステージ間のデータは `.cache/pipeline/` 以下の JSON ファイルで受け渡す。

## セットアップ

### 前提条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [VOICEVOX](https://voicevox.hiroshiba.jp/)（ローカルで起動しておく）
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

## 使い方

### パイプライン一括実行

```bash
uv run python scripts/run_pipeline.py
```

### 個別ステージ実行（Claude Code コマンド）

Claude Code 内で各コマンドを個別に実行できる。

```
/fetch-news
/process
/gen-script
/gen-metadata
/gen-video
/review-video
/upload
```

## プロジェクト構成

```
src/news_video_maker/
  config.py          # 設定読み込み
  pipeline.py        # パイプライン制御
  history.py         # 投稿履歴管理
  fetcher/
    rss.py           # RSS フィード取得
    models.py        # データモデル
  video/
    tts.py           # VOICEVOX 音声合成
    visuals.py       # 映像素材生成
    composer.py      # 動画合成
    background.py    # 背景生成
  uploader/
    youtube.py       # YouTube アップロード
specs/               # 仕様書
.claude/commands/     # Claude Code カスタムコマンド
scripts/              # パイプラインスクリプト
output/               # 生成動画
.cache/               # 中間ファイル（音声・画像・パイプラインデータ）
```

## 仕様書

各モジュールの詳細な仕様は `specs/` ディレクトリを参照。

## ライセンス

Private

# /upload

生成した動画を YouTube にアップロードする。

## 手順

### ステップ1: メタデータ生成

`/gen-metadata` コマンドと同じ手順でメタデータを生成し、`.cache/pipeline/05_metadata.json` に保存する。
（メタデータのみ再生成したい場合は `/gen-metadata` を単独で実行する）

### ステップ2: YouTube アップロード（Python実行）

Bash ツールで以下を実行（`--publish-at` は省略可能）:

```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.uploader.youtube [--publish-at YYYY-MM-DDTHH:MM:SSZ]
```

`--publish-at` を指定した場合、動画は `private` でアップロードされ、指定日時（UTC）に自動公開される。

実行後、YouTube URL を報告する。

## 前提条件

- `.env` に `YOUTUBE_CLIENT_SECRET_PATH` が設定されていること
- `.cache/pipeline/04_video_path.txt` が存在すること
- `.cache/pipeline/02_selected.json` と `.cache/pipeline/03_script.json` が存在すること
- `.cache/pipeline/05_metadata.json` は本コマンドが自動生成する（存在しない場合は `youtube.py` がフォールバック動作）

## チャンネルブランディング設定（.env）

以下の環境変数で動画の説明文・タグ・公開設定をカスタマイズできる:

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `CHANNEL_NAME` | `AIニュース1分解説` | 動画のhookバッジに表示されるチャンネル名 |
| `CHANNEL_HASHTAGS` | `#AIニュース #テックニュース ...` | descriptionとタグに使うハッシュタグ |
| `CHANNEL_DESCRIPTION_FOOTER` | `海外の最新AI・テックニュースを...` | descriptionのフッター文 |
| `YOUTUBE_PRIVACY` | `public` | 公開設定（`public` / `unlisted` / `private`） |

## 初回認証

初回実行時はブラウザで Google OAuth 認証画面が開く。
認証後は `token.json` にキャッシュされ、次回以降は自動認証される。

## エラー処理

- `client_secret.json` が見つからない場合: 取得手順を案内して停止
- クォータ超過: 翌日以降の再試行を促して停止（動画ファイルは保持）
- 認証失敗: `token.json` を削除して再認証を促す

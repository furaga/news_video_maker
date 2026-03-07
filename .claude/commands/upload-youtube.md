# /upload

生成した動画を YouTube にアップロードする。

## 手順

### ステップ1: メタデータ生成

`/gen-metadata` コマンドと同じ手順でメタデータを生成し、`.cache/pipeline/05_metadata.json` に保存する。
（メタデータのみ再生成したい場合は `/gen-metadata` を単独で実行する）

### ステップ2: YouTube アップロード（Python実行）

Bash ツールで以下を実行:

```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.uploader.youtube
```

実行後、YouTube URL を報告する。

## 前提条件

- `.env` に `YOUTUBE_CLIENT_SECRET_PATH` が設定されていること
- `.cache/pipeline/04_video_path.txt` が存在すること
- `.cache/pipeline/02_selected.json` と `.cache/pipeline/03_script.json` が存在すること
- `.cache/pipeline/05_metadata.json` は本コマンドが自動生成する（存在しない場合は `youtube.py` がフォールバック動作）

## 初回認証

初回実行時はブラウザで Google OAuth 認証画面が開く。
認証後は `token.json` にキャッシュされ、次回以降は自動認証される。

## エラー処理

- `client_secret.json` が見つからない場合: 取得手順を案内して停止
- クォータ超過: 翌日以降の再試行を促して停止（動画ファイルは保持）
- 認証失敗: `token.json` を削除して再認証を促す

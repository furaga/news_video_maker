# 仕様書: YouTube投稿（YouTube Uploader）

## 目的

生成した MP4 動画を YouTube Data API v3 を使って YouTube Shorts として投稿する。

## 対応コマンド

`.claude/commands/upload-youtube.md` → `/upload`

## 担当

Python（google-api-python-client）
コマンドは `src/news_video_maker/uploader/youtube.py` を Bash ツールで呼び出す。

---

## 入力

- **動画パス**: `.cache/pipeline/04_video_path.txt`（動画ファイルの絶対パス）
- **メタデータ**: `.cache/pipeline/02_selected.json`（タイトル・要約・ソースURL）と `.cache/pipeline/03_script.json`（動画タイトル）

---

## 出力

- **URLファイル**: `.cache/pipeline/05_youtube_url.txt`（投稿した動画の URL）
- 標準出力: YouTube URL を表示

---

## 認証

YouTube Data API v3 は OAuth 2.0 で認証する。

### 初回認証フロー

1. `.env` の `YOUTUBE_CLIENT_SECRET_PATH` からクライアントシークレット JSON を読み込む
2. ブラウザで Google OAuth 同意画面を開く（`InstalledAppFlow`）
3. 認証後のトークンを `token.json` にキャッシュする（`.gitignore` 済み）

### 2回目以降

1. `token.json` からトークンを読み込む
2. 期限切れの場合は自動リフレッシュ

---

## 投稿設定

### メタデータ

| フィールド | 値 |
|---|---|
| タイトル | `03_script.json` の `title`（最大 100 文字） |
| 説明文 | 下記テンプレート参照 |
| タグ | `["tech news", "テックニュース", "テクノロジー", "ShortNews", {source}]` |
| カテゴリ ID | `28`（Science & Technology） |
| プライバシー | 設定値（デフォルト: `unlisted`） |
| 字幕言語 | `ja` |

### 説明文テンプレート

```
{japanese_summary}

元記事: {source_url}

---
このチャンネルでは海外テックニュースを日本語で毎日お届けします。

#テックニュース #テクノロジー #ShortNews
```

### YouTube Shorts として認識させる条件

- 動画の縦横比が 9:16 であること（1080x1920 ✓）
- 動画の長さが 60 秒以内であること
- タイトルまたは説明文に `#Shorts` を含めることを**推奨**（任意で追加可能）

---

## 振る舞い

1. 入力ファイルを読み込む
2. OAuth 2.0 認証（`token.json` があれば自動）
3. YouTube Data API v3 の `videos.insert` でアップロード
   - **Resumable Upload** を使用（大容量ファイルに対応）
4. 進捗を表示（アップロード中）
5. 完了したら YouTube URL（`https://youtu.be/{video_id}`）を取得
6. `.cache/pipeline/05_youtube_url.txt` に URL を書き込む
7. URL を標準出力に表示

---

## モジュール構成

### `src/news_video_maker/uploader/youtube.py`

```python
# YouTube Data API v3 アップロード
# 入力: 動画パス, メタデータ dict, プライバシー設定
# 出力: YouTube URL (str)
def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy: str = "unlisted",
) -> str: ...
```

---

## エラー処理

- **認証失敗**: `token.json` を削除して再認証を促すメッセージを表示
- **アップロード失敗**: リトライ 3 回（指数バックオフ: 10秒, 20秒, 40秒）
- **クォータ超過** (`quotaExceeded`): エラーを表示し、翌日以降の再試行を促す。動画ファイルは保持する
- **動画ファイルが存在しない**: エラーを raise して停止

---

## 実装ノート

- `google-api-python-client` の `MediaFileUpload` を使った Resumable Upload
- `use context7` で `google-api-python-client` の最新 YouTube Data API v3 の使い方を確認すること
- YouTube API のスコープ: `https://www.googleapis.com/auth/youtube.upload`
- YouTube API の1日のクォータ: 10,000 ユニット（`videos.insert` は 1,600 ユニット）

---

## テスト方針

- `tests/uploader/test_youtube.py`
- YouTube API 呼び出しはモック（`pytest-mock`）
- 正常系: アップロード成功時に URL が返ること
- 異常系: クォータ超過時にエラーメッセージが出ること
- 認証フローはモックまたはスキップ（E2E テストは実際のアカウントで手動確認）

# 仕様書: スケジューラー / 記事履歴管理

## 目的

1. **記事履歴管理**: 投稿済み記事URLを永続化し、同じ記事の重複処理を防ぐ
2. **定期実行**: Windowsタスクスケジューラーを使ってパイプラインを自動実行する

---

## Feature 1: 記事履歴（HistoryStore）

### 履歴ファイル

- パス: `.cache/history.json`
- バージョン管理対象外（`.gitignore` の `.cache` ルールで除外済み）

### スキーマ

```json
{
  "version": 1,
  "entries": [
    {
      "url": "https://...",
      "title": "記事タイトル",
      "source": "techcrunch",
      "uploaded_at": "2026-03-07T15:30:00+00:00",
      "youtube_url": "https://youtu.be/xxxxx"
    }
  ]
}
```

### モジュール

`src/news_video_maker/history.py` に `HistoryStore` クラスを実装。

| メソッド | 役割 |
|---|---|
| `__init__(path)` | ファイルからロード |
| `seen_urls() -> set[str]` | 投稿済みURLセットを返す |
| `is_seen(url) -> bool` | 重複チェック |
| `record(url, title, source, youtube_url)` | 記録して即時保存 |

### Stage 1 への組み込み（rss.py）

`fetch_articles()` 内で:
1. `HistoryStore` をインスタンス化し `seen_urls()` を取得
2. 既存の `seen_urls` セットをこの値で初期化（既存のURLチェックロジックはそのまま流用）
3. `total_valid` カウンターで「時刻・URL形式チェック通過数（dedup前）」を記録

終了条件の区別:
- `total_valid == 0` → `RuntimeError`（フィード障害）
- `articles` が空 → `[]` を返す（新規記事なし）

`main()` は `fetch_articles()` が `[]` を返したとき `sys.exit(0)` で正常終了。

### Stage 5 への組み込み（youtube.py）

`upload_video()` 成功後、`url_file.write_text()` の直後に:

```python
try:
    HistoryStore().record(url=source_url, title=title, source=source, youtube_url=url)
except Exception as e:
    logger.warning("履歴記録失敗: %s", e)
```

`--dry-run` 時は Stage 5 自体がスキップされるため、`youtube.py` 内での判定は不要。

### エラー処理

| ケース | 動作 |
|---|---|
| `history.json` が存在しない | 空ヒストリーで起動（初回実行） |
| `history.json` が壊れている | 警告ログを出し、空ヒストリーで起動 |
| `record()` の保存失敗 | 警告ログのみ（アップロード成功を取り消さない） |

---

## Feature 2: 定期実行（Windowsタスクスケジューラー）

### エントリポイント

`scripts/run_pipeline.bat` をタスクスケジューラーに登録する。

```bat
@echo off
cd /d %~dp0..
uv run python scripts/run_pipeline.py >> logs\scheduler.log 2>&1
```

### タスクスケジューラー登録（PowerShell）

```powershell
$action = New-ScheduledTaskAction `
    -Execute "C:\Users\furag\Documents\prog\python\news_video_maker\scripts\run_pipeline.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At "08:00AM"
$settings = New-ScheduledTaskSettingsSet -RunOnlyIfNetworkAvailable
Register-ScheduledTask `
    -TaskName "NewsVideoMaker" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings
```

または GUI: タスクスケジューラー → 基本タスクの作成 → 毎日 → 時刻指定 → プログラム: `scripts\run_pipeline.bat`

### 動作

- 毎日指定時刻にパイプラインを実行する
- `history.json` により重複記事は自動スキップされる
- ログは `logs/scheduler.log` に追記される

---

## 実装対象ファイル

| ファイル | 変更種別 |
|---|---|
| `src/news_video_maker/history.py` | 新規 |
| `src/news_video_maker/config.py` | 修正（`HISTORY_PATH` 追加） |
| `src/news_video_maker/fetcher/rss.py` | 修正（履歴フィルタ、graceful exit） |
| `src/news_video_maker/uploader/youtube.py` | 修正（アップロード後に履歴記録） |
| `.claude/commands/run-pipeline.md` | 修正（空記事チェック追加） |
| `scripts/run_pipeline.bat` | 新規 |

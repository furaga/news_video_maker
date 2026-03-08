# /run-pipeline

ニュース取得から YouTube 投稿まで全ステージを順次実行する。

## 引数

- `--dry-run` / `--skip-upload`: 動画生成まで実行し、YouTube 投稿をスキップ
- `--from-stage N`: ステージ N から再開（1=fetch, 2=process, 3=script, 4=video, 5=upload）

## 実行手順

引数を確認して開始ステージを決定し、各ステージを順次実行する。

### ステージ 1: ニュース取得
`--from-stage` が 1 以下の場合、/fetch-news コマンドを実行:
```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.fetcher.rss
```

ステージ 1 完了後、`.cache/pipeline/01_articles.json` を読み込み、配列が空（`[]`）なら「新規記事なし」として後続ステージをスキップし、report.md に「新規記事なし: 処理済み記事のみのため終了」と記録して終了する。

### ステージ 2: 記事選定・日本語要約
`--from-stage` が 2 以下の場合、以下を実行:
- Read ツールで `.cache/pipeline/01_articles.json` を読み込む
- 記事をスコアリングして最良の1件を選定
- 日本語タイトル・要約・キーポイントを生成
- Write ツールで `.cache/pipeline/02_selected.json` に保存

### ステージ 3: 台本生成
`--from-stage` が 3 以下の場合、以下を実行:
- Read ツールで `.cache/pipeline/02_selected.json` を読み込む
- 30〜60秒の台本を生成（hook/main/outro の3セクション）
- Write ツールで `.cache/pipeline/03_script.json` に保存

### ステージ 4: 動画生成
`--from-stage` が 4 以下の場合、以下を実行:
```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.video.composer
```

### ステージ 4.5: 動画検証（技術チェック + フレーム抽出）
ステージ 4 完了後に以下を実行:
```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.video.validator
```
- 終了コード 1 の場合（`ok: false`）: エラーを report.md に記録してパイプラインを停止する
- 成功時: `.cache/pipeline/04_validation.json` と `.cache/pipeline/frames/` が生成される

### ステージ 4.6: 動画検証（視覚チェック）
`/validate-video` コマンドを実行して Claude Code にフレームを目視確認させる。
- 視覚チェック NG の場合はエラー内容を report.md に記録してパイプラインを停止する

### ステージ 5: YouTube 投稿
`--dry-run` でない場合かつ `--from-stage` が 5 以下の場合、以下を順に実行:

1. **メタデータ生成**: `/gen-metadata` コマンドと同じ手順を実行し `.cache/pipeline/05_metadata.json` に保存

2. **YouTube アップロード（Python実行）**:
   ```bash
   cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.uploader.youtube
   ```

## 完了後

全ステージ完了後、Write ツールで `report.md` を以下の形式で生成:

```markdown
# 実行レポート: YYYY-MM-DD HH:MM

## 結果: 成功 / 失敗

## 取得記事数
- 合計: X件

## 選定記事
- タイトル: ...
- ソース: ...
- スコア: ...

## 生成動画
- パス: output/YYYYMMDD_HHMMSS.mp4
- 尺: XX秒

## YouTube
- URL: https://youtu.be/xxxxx（--dry-run の場合は「スキップ」）
- プライバシー: unlisted

## エラー（あれば）
- ...
```

## エラー処理

- 各ステージ失敗時はエラー内容を report.md に記録してパイプラインを停止する
- `--from-stage` で失敗したステージから再実行可能

# Codex 動画生成パイプライン

末尾の実行パラメータに従い、取得から動画生成・検証・予約投稿まで順次完了する。
これはソースコード変更の依頼ではない。Pythonツールと生成データを扱う運用タスクである。

## 共通ルール

- 作業ディレクトリは起動時のプロジェクトルート。古い絶対パスへの `cd` は行わない。
- `PIPELINE_RUN_ID` は設定済み。全手順の `.cache/pipeline/` を
  `.cache/pipeline/{run_id}/` と読み替える。すでにrun_idが含まれるパスに二重追加しない。
- `.claude/commands/` の参照先は品質基準とデータ形式の共通仕様として読む。
  スラッシュコマンド、Skill、Claude SDK、Claude専用サブエージェントは呼ばず、
  読み書き・検索・画像表示・シェル実行をCodexのツールで直接行う。
  Readによる画像確認は必ず画像表示ツールで行う。WebSearch/WebFetchは利用可能な検索・取得機能で行う。
- 参照先の確認要求は生成結果の自己検証として処理する。必要な機能や権限がなく完了できない場合は
  成功扱いせず `failed` とする。手順の省略や検証結果の捏造は禁止。
- シェルの構文は実際のOSに合わせる。Pythonは `uv run python` で実行する。
- ソースコード、設定、認証ファイルの内容を表示・変更しない。既存ツールによる認証更新は許容する。
- 各処理の要点を `logs/<yyyymmdd>/` に記録し、最後に `report.md` に
  run_id、mode、結果、取得件数、選定内容、動画パス・尺、YouTube URL、コメント結果、エラーを記録する。
- 中間成果物だけで完了しない。失敗時は後続の生成・投稿を止める。

## 手順

1. `from_stage <= 1` の場合のみ取得する。
   - news: `uv run python -m news_video_maker.fetcher.rss`。
     標準出力が「新規記事なし」で始まる場合は `no_content` として終了する。
     選定には `01_articles_index.json` を使い、大きな `01_articles.json` 全体は読まない。
   - paper: `uv run python -m news_video_maker.fetcher.paper`。
     `01_papers.json` が空配列の場合は `no_content` として終了する。
   - コマンド失敗時は `failed`。新規なしでもreport.mdを記録する。
2. `from_stage <= 2` の場合のみ選定・日本語要約を行う。
   newsは `.claude/commands/process-article.md`、paperは `process-paper.md` を読み実行する。
   `02_selected.json` が生成され、参照先のスキーマを満たすことを確認する。
3. `from_stage <= 3` の場合のみ台本を生成する。
   newsは `.claude/commands/generate-script.md`、paperは `generate-script-paper.md` を読み実行する。
   `03_script.json` を検証して次に進む。
4. `from_stage <= 4` の場合、スクリーンショットと動画を生成する。
   - `uv run python -m news_video_maker.video.screenshot` を実行する。
   - `.cache/images/{run_id}/article_screenshot_full.png` が生成された場合は画像として開き、
     白画面、ログイン画面、エラーページでないことを確認する。
     無効ならこの画像だけを削除し、composerの背景画像フォールバックを使う。
     撮影失敗時もフォールバックへ進み、レポートに記録する。
   - `uv run python -m news_video_maker.video.composer` を実行する。失敗なら停止する。
5. 再開時も投稿前の検証を省略しない。
   - `uv run python -m news_video_maker.video.validator` を実行する。
     終了コードが非ゼロ、または `04_validation.json` の `ok` がfalseなら停止する。
   - `.claude/commands/validate-video.md` を読み、全フレームを画像表示して視覚検証する。
     `04_validation.json` の `ok` と `visual_check.ok` が両方trueであることを確認する。
     画像表示機能が使えない場合も停止する。
6. `dry_run=true` ならアップロードとコメント投稿を一切行わず、検証済み動画の報告で終了する。
7. `dry_run=false` なら次を順に行う。
   - `.claude/commands/generate-metadata.md` の手順で `05_metadata.json` と `05_comment.txt` を生成・検証する。
   - `uv run python -m news_video_maker.uploader.youtube` を実行する。
     `publish_at` が空でなければ `--publish-at` にその値を引用して渡す。
   - 成功後、`05_youtube_url.txt` から動画IDを、`03_script.json` からtitleを取得し、
     `uv run python scripts/post_comments.py --video-id <ID> --comment-file <05_comment.txtのパス> --title <title>`
     を実行する。引数はシェルに合わせて適切に引用する。
     `.cache/youtube_comments.md` は読み書きしない。コメントだけの失敗は警告を記録し、全体は成功とする。

## 最終応答

report.mdを保存した後、指定されたJSONスキーマに従い最終応答する。
`status` は全工程完了なら `success`、新規コンテンツなしなら `no_content`、
それ以外の失敗・中断なら `failed`。`summary` に日本語で結果・エラーを短く記載する。

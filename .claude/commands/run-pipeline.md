# /run-pipeline

ニュース取得または論文取得から YouTube 投稿まで全ステージを順次実行する。

## 引数

- `--mode news|paper`: 実行モード（デフォルト: `news`）
  - `news`: 海外テックニュース記事モード（従来動作）
  - `paper`: 最新技術論文モード（arXiv + HF Daily Papers）
- `--dry-run` / `--skip-upload`: 動画生成まで実行し、YouTube 投稿をスキップ
- `--from-stage N`: ステージ N から再開（1=fetch, 2=process, 3=script, 4=video, 5=upload）
- `--run-id ID`: 実行ID（省略時は自動生成済み）。キャッシュパスは `.cache/pipeline/{run_id}/` になる
- `--publish-at ISO8601`: YouTube 公開スケジュール時刻（UTC ISO 8601 形式）。例: `2026-03-12T23:00:00Z`

## 実行手順

> **重要（エージェントへの指示）**: 各ステージで Skill ツールや Bash を使ってコマンドを実行した後も、
> **全ステージが完了するまでこのセッションを終了しないこと**。
> あるステージの完了は「パイプライン全体の完了」ではなく「次のステージに進む合図」である。

引数を確認して開始ステージと実行モードを決定し、各ステージを順次実行する。

`--run-id` が指定された場合、以下の全ファイルパスの `.cache/pipeline/` を `.cache/pipeline/{run_id}/` に読み替えて実行する。

### ステージ 1: 取得

**`--mode news`（デフォルト）の場合**、/fetch-news コマンドを実行:
```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.fetcher.rss
```
完了後、`.cache/pipeline/{run_id}/01_articles.json` を読み込み、配列が空（`[]`）なら「新規記事なし」として後続ステージをスキップし、report.md に「新規記事なし: 処理済み記事のみのため終了」と記録して終了する。

**`--mode paper` の場合**、/fetch-papers コマンドを実行:
```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.fetcher.paper
```
完了後、`.cache/pipeline/{run_id}/01_papers.json` を読み込み、配列が空（`[]`）なら「新規論文なし」として後続ステージをスキップし、report.md に「新規論文なし: 処理済み論文のみのため終了」と記録して終了する。

（`PIPELINE_RUN_ID` 環境変数が設定済みのため、Python側が自動的に正しいディレクトリへ書き込む）

### ステージ 2: 選定・日本語要約

`--from-stage` が 2 以下の場合、以下を実行:

**`--mode news` の場合**: `/process` コマンドと同じ手順を実行する:

1. **過去採用タイトルを取得（ネタ被り防止）**:
   - Bash で `.cache/pipeline/` 以下の全 `02_selected.json` を列挙する:
     ```bash
     ls .cache/pipeline/*/02_selected.json 2>/dev/null
     ```
   - 見つかったファイル（現在の `{run_id}` のものは除く）を Read ツールで読み込み、`title`（英語原題）と `japanese_title`（日本語タイトル）を収集し `past_titles` リストとして保持する
   - ファイルが1件もない場合は `past_titles = []` とする

2. **記事をスコアリングして最良の1件を選定**:
   - Read ツールで `.cache/pipeline/{run_id}/01_articles.json` を読み込む
   - 各記事を 1〜10 点でスコアリング。以下の**視聴数パターン**に基づいて加点・減点する:

   **加点要素（高視聴に繋がる傾向）:**
   - 個人の体験・実話ストーリー形式（「〇〇した話」「〇〇になった」）: **+3点**
   - お金・給与・報酬・賞金など金額が絡む内容: **+2点**
   - 「自分ごと」として感じられる内容（自分の仕事・スマホ・使っているサービスに関係する）: **+2点**
   - 業界ドラマ（著名人の辞任・抗議・対立・スキャンダル）: **+2点**
   - 驚き・意外性・皮肉なオチがある（逆説的な展開）: **+1点**

   **減点要素（低視聴に繋がる傾向）:**
   - 抽象的・汎用的すぎるテーマ（「〇〇の常識が変わった」など）: **-2点**
   - 特定地域・ニッチ企業のニュースで日本人視聴者に馴染みが薄い: **-2点**
   - 製品レビュー・スペック紹介のみで人間ドラマがない: **-1点**
   - `past_titles` に含まれる過去記事と主題・企業・技術が重複または類似する場合は **-10点** のペナルティ（ネタ被り防止）

   採点した結果、最高スコアの記事を選定する

1. **日本語タイトル・要約・キーポイントを生成**

2. **Write ツールで `.cache/pipeline/{run_id}/02_selected.json` に保存**

**`--mode paper` の場合**: `/process-paper` コマンドと同じ手順を実行する:

1. **過去採用タイトルを取得（ネタ被り防止）**:
   - 上記 news モードと同様に `past_titles` を取得する

2. **論文をスコアリングして最良の1件を選定**:
   - Read ツールで `.cache/pipeline/{run_id}/01_papers.json` を読み込む
   - 各論文を 1〜10 点でスコアリング（HF 掲載 +2 点、技術的新規性・実用性・分かりやすさを考慮）
   - `past_titles` との重複は **-3点** ペナルティ
   - 最高スコアの論文を選定（同点は `hf_upvotes` 多い順 → 新しい順）

3. **日本語タイトル・要約・キーポイントを生成**

4. **Write ツールで `.cache/pipeline/{run_id}/02_selected.json` に保存**

### ステージ 3: 台本生成

`--from-stage` が 3 以下の場合、以下を実行:
- Read ツールで `.cache/pipeline/{run_id}/02_selected.json` を読み込む

**`--mode news` の場合**: `/gen-script` コマンドと同じ手順で台本を生成する。
**`--mode paper` の場合**: `/gen-script-paper` コマンドと同じ手順で台本を生成する（セクション構成が論文向けに最適化）。

- Write ツールで `.cache/pipeline/{run_id}/03_script.json` に保存
- **台本を保存したらセッションを終了せず、直ちにステージ3.5（スクリーンショット検証）に進む。**

### ステージ 3.5: スクリーンショット検証

`--from-stage` が 4 以下の場合、以下を実行:

1. スクリーンショットを撮影:
```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.video.screenshot
```

2. 撮影に成功した場合、Read ツールで `.cache/images/{run_id}/article_screenshot_full.png` を読み込む（画像として表示される）

3. 画像が有効な記事スクリーンショットかを判定する:
   - 記事のテキストや画像など、実際のウェブページコンテンツが表示されているか
   - 白画面・空白ページ・ブラウザのログイン画面・エラーページではないか

4. **無効な場合**: 画像ファイルを削除する:
   ```bash
   rm .cache/images/{run_id}/article_screenshot_full.png
   ```
   → ステージ4で composer が SD 生成画像を自動的に hook セクションに使用する

5. **有効な場合**: そのまま次のステージに進む

### ステージ 4: 動画生成

`--from-stage` が 4 以下の場合、以下を実行:
```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.video.composer
```
（`PIPELINE_RUN_ID` 環境変数が設定済みのため、Python側が自動的に正しいディレクトリから読み込む）

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

1. **メタデータ生成**: `/gen-metadata` コマンドと同じ手順を実行し `.cache/pipeline/{run_id}/05_metadata.json` に保存

2. **YouTube アップロード（Python実行）**:

   `--publish-at` が指定されている場合:
   ```bash
   cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.uploader.youtube --publish-at {publish_at}
   ```
   指定されていない場合:
   ```bash
   cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.uploader.youtube
   ```

3. **投稿者コメント投稿（Bash実行）**:

   `.cache/pipeline/{run_id}/05_youtube_url.txt` を Read ツールで読み込み、URL から VIDEO_ID（`https://youtu.be/` 以降の文字列）を取得して実行:
   ```bash
   cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python scripts/post_comments.py --video-id {VIDEO_ID}
   ```
   - エラーが出ても（認証未初期化・API エラーなど）パイプライン全体は停止しない
   - 結果（コメント ID またはエラー内容）を report.md の YouTube セクションに記録する

## 完了後

全ステージ完了後、Write ツールで `report.md` を以下の形式で生成:

```markdown
# 実行レポート: YYYY-MM-DD HH:MM

## 実行ID
- run_id: {run_id}
- mode: news / paper

## 結果: 成功 / 失敗

## 取得件数
- 合計: X件（news: 記事数 / paper: 論文数）

## 選定コンテンツ
- タイトル: ...
- ソース: ...（news: techcrunch など / paper: arxiv）
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

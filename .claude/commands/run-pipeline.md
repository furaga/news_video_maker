# /run-pipeline

ニュース取得または論文取得から YouTube 投稿まで全ステージを順次実行する。

## 引数

- `--mode news|paper|trivia|space`: 実行モード（デフォルト: `news`）
  - `news`: 海外テックニュース記事モード（従来動作）
  - `paper`: 最新技術論文モード（arXiv + HF Daily Papers）
  - `trivia`: 雑学・豆知識モード（OpenTDB）
  - `space`: 宇宙・天文モード（NASA APOD + RSS）
- `--dry-run` / `--skip-upload`: 動画生成まで実行し、YouTube 投稿をスキップ
- `--from-stage N`: ステージ N から再開（1=fetch, 2=process, 3=script, 4=video, 5=upload）
- `--run-id ID`: 実行ID（省略時は自動生成済み）。キャッシュパスは `.cache/pipeline/{run_id}/` になる
- `--publish-at ISO8601`: YouTube 公開スケジュール時刻（UTC ISO 8601 形式）。例: `2026-03-12T23:00:00Z`

## 実行手順

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

**`--mode trivia` の場合**、/fetch-trivia コマンドを実行:
```bash
cd /c/Users/furag/Documents/prog/python/wt-new-themes && uv run python -m news_video_maker.fetcher.trivia
```
完了後、`.cache/pipeline/{run_id}/01_trivia.json` を読み込み、配列が空（`[]`）なら「新規雑学なし」として後続ステージをスキップし、report.md に「新規雑学なし: 処理済みデータのみのため終了」と記録して終了する。

**`--mode space` の場合**、/fetch-space コマンドを実行:
```bash
cd /c/Users/furag/Documents/prog/python/wt-new-themes && uv run python -m news_video_maker.fetcher.space
```
完了後、`.cache/pipeline/{run_id}/01_space.json` を読み込み、配列が空（`[]`）なら「新規宇宙コンテンツなし」として後続ステージをスキップし、report.md に「新規宇宙コンテンツなし: 処理済みデータのみのため終了」と記録して終了する。

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

**`--mode trivia` の場合**: `/process-trivia` コマンドと同じ手順を実行する:

1. **過去採用タイトルを取得（ネタ被り防止）**: 上記と同様
2. **雑学データをスコアリング**: `01_trivia.json` を読み込み、驚き度・視覚性・汎用性でスコアリング
3. **Wikipedia API から image_url を取得**: `https://en.wikipedia.org/api/rest_v1/page/summary/{KEYWORD}` → `thumbnail.source`
4. **日本語タイトル・要約・キーポイントを生成**
5. **Write ツールで `.cache/pipeline/{run_id}/02_selected.json` に保存**

**`--mode space` の場合**: `/process-space` コマンドと同じ手順を実行する:

1. **過去採用タイトルを取得（ネタ被り防止）**: 上記と同様
2. **宇宙コンテンツをスコアリング**: `01_space.json` を読み込み、視覚的魅力・発見度・スケール感でスコアリング（APOD 優先）
3. **日本語タイトル・要約・キーポイントを生成**
4. **Write ツールで `.cache/pipeline/{run_id}/02_selected.json` に保存**

### ステージ 3: 台本生成

`--from-stage` が 3 以下の場合、以下を実行:
- Read ツールで `.cache/pipeline/{run_id}/02_selected.json` を読み込む

**`--mode news` の場合**: `/gen-script` コマンドと同じ手順で台本を生成する。
**`--mode paper` の場合**: `/gen-script-paper` コマンドと同じ手順で台本を生成する（セクション構成が論文向けに最適化）。
**`--mode trivia` の場合**: `/gen-script-trivia` コマンドと同じ手順で台本を生成する（クイズ→驚き→解説構成）。
**`--mode space` の場合**: `/gen-script-space` コマンドと同じ手順で台本を生成する（スケール→発見→感動構成）。

- Write ツールで `.cache/pipeline/{run_id}/03_script.json` に保存

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

## 完了後

全ステージ完了後、Write ツールで `report.md` を以下の形式で生成:

```markdown
# 実行レポート: YYYY-MM-DD HH:MM

## 実行ID
- run_id: {run_id}
- mode: news / paper / trivia / space

## 結果: 成功 / 失敗

## 取得件数
- 合計: X件（news: 記事数 / paper: 論文数 / trivia: 雑学数 / space: 宇宙コンテンツ数）

## 選定コンテンツ
- タイトル: ...
- ソース: ...（news: techcrunch など / paper: arxiv / trivia: opentdb / space: nasa_apod など）
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

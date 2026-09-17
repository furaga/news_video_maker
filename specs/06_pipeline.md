# 仕様書: パイプライン統合（Pipeline）

## 目的

5つのステージ（fetch → process → gen-script → gen-video → upload）を Claude Code のカスタムコマンドとして順次実行し、ニュース記事または最新技術論文から YouTube 投稿までを自動化する。

`--mode` 引数でニュースモード（従来）と論文モード（arXiv + HF Daily Papers）を切り替えられる。

## 対応コマンド

`.claude/commands/run-pipeline.md` → `/run-pipeline`

## 担当

Claude Agent SDK（Python）+ Claude Code カスタムコマンド

---

## アーキテクチャ

```
scripts/run_pipeline.py
  ↓ claude-agent-sdk
Claude Code CLI
  ↓ .claude/commands/ の各コマンドを順次実行

  --mode news（デフォルト）:
  1. /fetch-news    → .cache/pipeline/01_articles.json + 01_articles_index.json
  2. /process       → .cache/pipeline/02_selected.json
  3. /gen-script    → .cache/pipeline/03_script.json

  --mode paper:
  1. /fetch-papers  → .cache/pipeline/01_papers.json
  2. /process-paper → .cache/pipeline/02_selected.json（スキーマ共通）
  3. /gen-script-paper → .cache/pipeline/03_script.json（スキーマ共通）

  共通（mode によらず同一）:
  4. /gen-video     → output/*.mp4 + .cache/pipeline/04_video_path.txt
  5. /upload        → .cache/pipeline/05_youtube_url.txt
```

---

## 入力

なし（設定は `config.py` と `.env` から読み込む）

### CLI オプション（`scripts/run_pipeline.py`）

```
usage: run_pipeline.py [--mode MODE] [--dry-run] [--skip-upload] [--from-stage STAGE] [--run-id ID]

オプション:
  --mode MODE       実行モード: news（デフォルト）または paper
  --dry-run         動画生成まで実行し、YouTube 投稿をスキップ
  --skip-upload     --dry-run の別名
  --from-stage N    ステージ N から再開（1=fetch, 2=process, 3=script, 4=video, 5=upload）
  --run-id ID       実行ID（省略時は自動生成）。複数同時実行時にキャッシュを分離する
```

### 並列実行対応

`--run-id` を指定することで複数のパイプラインを同時に実行できる。

- 実行IDはデフォルトでタイムスタンプ（`YYYYMMDD_HHMMSS`）を自動生成
- 各実行のキャッシュファイルは `.cache/pipeline/{run_id}/` に格納される
- 音声・画像キャッシュも `.cache/audio/{run_id}/`, `.cache/images/{run_id}/` に分離される
- `PIPELINE_RUN_ID` 環境変数で Python ツール群に伝達される

---

## 出力

| ファイル | 内容 |
|---|---|
| `.cache/pipeline/01_articles.json` | 取得記事一覧（news モード） |
| `.cache/pipeline/01_articles_index.json` | 取得記事一覧から `full_text` を除いた選定用インデックス（news モード） |
| `.cache/pipeline/01_papers.json` | 取得論文一覧（paper モード） |
| `.cache/pipeline/02_selected.json` | 選定・要約済みコンテンツ（モード共通スキーマ） |
| `.cache/pipeline/03_script.json` | 台本 |
| `output/<timestamp>.mp4` | 生成動画 |
| `.cache/pipeline/04_video_path.txt` | 動画パス |
| `.cache/pipeline/05_youtube_url.txt` | YouTube URL（投稿した場合） |
| `report.md` | 実行サマリー（成功/失敗、YouTube URL など） |

---

## 振る舞い

### `scripts/run_pipeline.py`（Python + Claude Agent SDK）

1. 引数をパース
2. `.cache/pipeline/` ディレクトリを作成（存在しない場合）
3. `claude_agent_sdk` を使って Claude Code を起動
4. `/run-pipeline` コマンドを送信（引数を含む）
5. Claude Code の出力を標準出力に流す
6. 終了コードを受け取って返す

### Claude Agent SDK のモデル指定

`src/news_video_maker/pipeline.py` の `ClaudeAgentOptions` で `model="opus"` を明示指定する。

- `opus` は Claude Code のエイリアスで、実行時点の最新 Opus（現状 Claude Opus 5）に解決される
- `setting_sources=["project"]` のためユーザー設定の model は読み込まれない。scheduler / パイプライン実行でも Opus を使うため、コード側で固定する

### トークン効率化: サブエージェントによるステージ別モデル切替

パイプラインは 1 セッションで全ステージを順次実行する（ワークフローは変えない）。そのうえで、
品質への影響が小さく入力が大きいステージは `ClaudeAgentOptions.agents` で定義した
**サブエージェント**に委譲し、軽いモデルで実行する。

| サブエージェント | 担当ステージ | model | プロンプト | tools |
|---|---|---|---|---|
| `article-selector` | 2 選定・日本語要約（news） | `sonnet` | `.claude/commands/process-article.md` | Read, Write, WebSearch |
| `paper-selector` | 2 選定・日本語要約（paper） | `sonnet` | `.claude/commands/process-paper.md` | Read, Write, WebSearch |
| `video-checker` | 4.6 視覚チェック | `haiku` | `.claude/commands/validate-video.md` | Read, Write, Glob |
| `metadata-writer` | 5-1 メタデータ + 投稿者コメント生成 | `sonnet` | `.claude/commands/generate-metadata.md` | Read, Write, WebSearch, WebFetch |

- 台本生成（ステージ3）は動画の品質を直接決めるため親セッション（opus）のまま
- ステージ2は記事一覧・history・WebSearch 結果と入力が大きいため委譲する。倫理方針を含むスコアリング判断があるため haiku ではなく sonnet を使う（サブエージェント内で完結するため、モデル差による費用差は数セント）
- サブエージェントのプロンプトは対応するコマンドファイルを `pipeline.py` が起動時に読み込んで渡す（コマンドファイルが単一の正）。先頭に「`.cache/pipeline/` を `.cache/pipeline/{run_id}/` に読み替える」旨の前置きを付ける
- 親セッションは Agent ツールで `subagent_type` と run_id を含む短い prompt を渡すだけで、フレーム画像・WebSearch 結果・WebFetch 結果を自分のコンテキストに載せない
- 効果: モデル単価の差に加え、サブエージェントの入出力が親（opus）の以降の全ターンで再送されなくなる

### トークン効率化: 親セッションに載せない入力

- `01_articles.json` は `full_text`（生 HTML 断片）を含み数十KB になるため親セッションでは Read しない。選定は fetcher が出力する `01_articles_index.json`（`full_text` を除いた同一スキーマ）を用いる（`specs/01_news_fetcher.md`, `specs/02_content_processor.md`）
- `.cache/youtube_comments.md`（投稿済みコメントの記録。実行のたびに肥大化する）は LLM が読み書きしない。LLM は `05_comment.txt` のみ書き、投稿成功後に `scripts/post_comments.py` が `--title` で渡された動画タイトルと URL を付けて追記する（同じ URL があれば追記しない）

### 使用トークンのログ

`pipeline.py` は `ResultMessage.usage` を `[Usage] in=... cache_w=... cache_r=... out=...` の形式で
`logs/<yyyymmdd>/pipeline_<run_id>.log` に出力する（改善前後の比較用）。

### `.claude/commands/run-pipeline.md`（Claude Code コマンド）

1. `--from-stage` に応じて開始ステージを決定
2. 各ステージを順次実行（Bash ツール、他コマンドの呼び出し、またはサブエージェントへの委譲）
3. 各ステージの成否を確認して次に進む
4. `--dry-run` の場合は upload をスキップ
5. 最後に `report.md` を生成

---

## ステージ間の連携

各ステージは **ファイルベースのインターフェース** で連携する。前ステージの出力ファイルが存在しない場合は実行を停止し、エラーを表示する。

### `--from-stage` による再開

| `--from-stage` | 必要な入力ファイル |
|---|---|
| `1` (fetch) | なし |
| `2` (process) | `01_articles_index.json`（news）または `01_papers.json`（paper） |
| `3` (script) | `02_selected.json` |
| `4` (video) | `03_script.json` |
| `5` (upload) | `04_video_path.txt`, `02_selected.json`, `03_script.json` |

---

## `report.md` の形式

```markdown
# 実行レポート: YYYY-MM-DD HH:MM

## 結果: 成功 / 失敗

## 取得記事数
- 合計: 25件

## 選定記事
- タイトル: ...
- ソース: TechCrunch
- スコア: 8.5

## 生成動画
- パス: output/20260307_120000.mp4
- 尺: 45秒

## YouTube
- URL: https://youtu.be/xxxxx
- プライバシー: unlisted

## エラー（あれば）
- ...
```

---

## エラー処理

- **ステージ失敗**: ステージ名とエラー内容を `report.md` に記録し、パイプラインを停止
- **途中再開**: `--from-stage` で失敗したステージから再実行可能

---

## `src/news_video_maker/pipeline.py`（Claude Agent SDK 実装）

```python
# Claude Agent SDK を使って Claude Code を起動し、
# /run-pipeline コマンドを実行するオーケストレーター
import claude_agent_sdk

async def run(dry_run: bool = False, from_stage: int = 1) -> int:
    # Claude Code を起動してパイプラインを実行
    # 終了コードを返す
    ...
```

実装時は `claude-developer-platform` スキルを使用すること。

---

## テスト方針

- 各ステージ単体テストで個別確認
- パイプライン全体の E2E テストはサンプルデータを使って手動実行
- `--from-stage 3`（台本から）での動作確認も行う

---

## 実装順序（推奨）

1. `specs/01_news_fetcher.md` → `fetcher/rss.py` + `/fetch-news` コマンド
2. `specs/02_content_processor.md` → `/process` コマンド（Python実装不要）
3. `specs/03_script_generator.md` → `/gen-script` コマンド（Python実装不要）
4. `specs/04_video_generator.md` → `video/` モジュール + `/gen-video` コマンド
5. `specs/05_youtube_uploader.md` → `uploader/youtube.py` + `/upload` コマンド
6. `specs/06_pipeline.md` → `pipeline.py` + `/run-pipeline` コマンド + `run_pipeline.py`

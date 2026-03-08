# 仕様書: パイプライン統合（Pipeline）

## 目的

5つのステージ（fetch → process → gen-script → gen-video → upload）を Claude Code のカスタムコマンドとして順次実行し、ニュース記事から YouTube 投稿までを自動化する。

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
  1. /fetch-news    → .cache/pipeline/01_articles.json
  2. /process       → .cache/pipeline/02_selected.json
  3. /gen-script    → .cache/pipeline/03_script.json
  4. /gen-video     → output/*.mp4 + .cache/pipeline/04_video_path.txt
  5. /upload        → .cache/pipeline/05_youtube_url.txt
```

---

## 入力

なし（設定は `config.py` と `.env` から読み込む）

### CLI オプション（`scripts/run_pipeline.py`）

```
usage: run_pipeline.py [--dry-run] [--skip-upload] [--from-stage STAGE] [--run-id ID]

オプション:
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
| `.cache/pipeline/01_articles.json` | 取得記事一覧 |
| `.cache/pipeline/02_selected.json` | 選定・要約済み記事 |
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

### `.claude/commands/run-pipeline.md`（Claude Code コマンド）

1. `--from-stage` に応じて開始ステージを決定
2. 各ステージを順次実行（Bash ツールまたは他コマンドの呼び出し）
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
| `2` (process) | `01_articles.json` |
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

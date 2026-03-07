# 出力形式

最終的な出力はreport.mdにmarkdown形式で保存してください。

# 作業ログ出力

logs/<yyyymmdd>/以下に各ステップにおける作業ログ（調べた内容・考えていること・処理した内容・今後実行すべきこと）を残してください。

# コード生成

ソースコードを生成する場合は、人間が理解しやすく・修正しやすいようにシンプルなコードを生成することを心がけてください。

# プロジェクト固有の方針

## 仕様ドリブン実装

- 実装前に必ず `specs/` 以下の仕様書を確認・作成してから実装する
- 仕様書に記載のないふるまいを勝手に追加しない

## アーキテクチャ

- 各パイプラインステージは `.claude/commands/` にカスタムコマンドとして定義する
- LLM処理（要約・翻訳・台本生成）は Claude Code コマンド内で行う
- Python ツール群（`src/news_video_maker/`）は RSS取得・動画生成・YouTube投稿の実装に専念する
- ステージ間のデータは `.cache/pipeline/` 以下の JSON/テキストファイルで受け渡す

## ツール・ライブラリ

- Claude Agent SDK のコード実装時は `claude-developer-platform` スキルを使用する
- ライブラリのドキュメント参照が必要な場合は「use context7」を使用する
- パッケージ管理は `uv` を使用する（`uv add`, `uv sync`, `uv run`）

## APIキー・認証情報

- APIキーは `.env` に格納し、`python-dotenv` で読み込む
- `.env` は絶対にコミットしない（`.gitignore` で除外済み）
- `.env.example` にキーの一覧を記載する

## Git ブランチ運用

- **`origin/master` には直接 push しない**
- コード変更・機能追加の実装は必ず worktree + feature ブランチで行う
- worktree 作成時は `--track origin/master` を使わず、明示的に upstream を feature ブランチに設定する:
  ```bash
  git worktree add ../wt-xxx feature/xxx
  cd ../wt-xxx
  git push -u origin feature/xxx
  ```
- feature ブランチの merge は GitHub の PR 経由で行う（Claude が直接 master へ merge しない）

## 出力ファイル

- 生成動画: `output/` ディレクトリ
- 中間ファイル（音声・画像）: `.cache/` ディレクトリ
- パイプラインデータ: `.cache/pipeline/`

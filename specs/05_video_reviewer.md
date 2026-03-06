# 仕様書 05: 動画レビュー (Video Reviewer)

## 目的

生成済み動画を人間がレビューし、承認・修正依頼・却下を判断するステージ。
レビュー結果を `.cache/pipeline/05_review.json` に保存し、次のパイプラインステージ（YouTube投稿）へ引き継ぐ。

## 対応コマンド

`/review-video`

## 担当

Claude LLM（インタラクティブ入力補助）

---

## 入力

| ファイル | 必須 | 説明 |
|---|---|---|
| `.cache/pipeline/04_video_path.txt` | ✅ | 生成された動画ファイルのパス |
| `.cache/pipeline/03_script.json` | ✅ | 台本データ（参照用） |

### `03_script.json` のスキーマ（参照用）

```json
{
  "title": "動画タイトル",
  "hook": "冒頭ナレーション（5秒）",
  "main_narration": "本編ナレーション（20-40秒）",
  "outro": "アウトロナレーション（5秒）",
  "hashtags": ["#tag1", "#tag2"]
}
```

---

## 出力

`.cache/pipeline/05_review.json`

```json
{
  "video_path": "output/video_20240307_123456.mp4",
  "reviewed_at": "2024-03-07T12:34:56",
  "status": "approved",
  "feedback": "ナレーションのテンポが良い。承認。",
  "revision_targets": []
}
```

### フィールド定義

| フィールド | 型 | 説明 |
|---|---|---|
| `video_path` | string | レビューした動画ファイルのパス |
| `reviewed_at` | string | ISO 8601形式のレビュー日時 |
| `status` | string | `"approved"` / `"needs_revision"` / `"rejected"` |
| `feedback` | string | レビューコメント・フィードバック本文 |
| `revision_targets` | string[] | 修正対象（`"narration"` / `"visuals"` / `"timing"` / `"bgm"`）。`approved`・`rejected` の場合は空配列 |

---

## 振る舞い

### 通常フロー

1. `.cache/pipeline/04_video_path.txt` を読み込んで動画ファイルパスを取得する
2. `.cache/pipeline/03_script.json` を読み込んで台本内容を取得する
3. 動画ファイルが存在するか確認する
4. 台本の内容をレビュアーに提示する（hook・main_narration・outro）
5. 動画ファイルのパスを表示し、視聴を促す
6. レビュアーに判定の入力を求める
   - `approved`（承認）
   - `needs_revision`（修正依頼）
   - `rejected`（却下）
7. `needs_revision` の場合、追加でフィードバックを入力させる
   - 修正対象（複数選択可）: `narration` / `visuals` / `timing` / `bgm`
   - 具体的な修正コメント（自由記述）
8. 現在日時を取得して `reviewed_at` を生成する
9. `.cache/pipeline/05_review.json` に保存する
10. 結果サマリを表示する

### `$ARGUMENTS` による即時実行

コマンド引数に `approved` / `needs_revision` / `rejected` を渡すと、ステータスを即時設定できる。
フィードバックは引数に続くテキストとして解釈する。

例:
- `/review-video approved` → 承認で即時保存
- `/review-video needs_revision ナレーションが速すぎる` → 修正依頼とフィードバックを保存

---

## エラー処理

| 条件 | 対応 |
|---|---|
| `04_video_path.txt` が存在しない | エラーメッセージを表示して終了（`/gen-video` を先に実行するよう案内） |
| `03_script.json` が存在しない | 警告を表示するが処理は続行（台本なしでレビュー可能） |
| 動画ファイルが存在しない | 警告を表示するが処理は続行（パスは保存） |
| 無効な `status` 入力 | 再入力を促す |
| `.cache/pipeline/` ディレクトリが存在しない | 自動作成する |

---

## テスト方針

### 手動テスト

1. サンプルファイルを手動作成:
   ```
   echo "output/test_video.mp4" > .cache/pipeline/04_video_path.txt
   ```
2. `/review-video` を実行し、インタラクティブフローを確認する
3. `/review-video approved` を実行し、即時保存を確認する
4. 生成された `05_review.json` の内容を検証する

### 検証ポイント

- `status` フィールドが正しく保存されるか
- `reviewed_at` が ISO 8601 形式か
- `needs_revision` 時に `revision_targets` が正しく保存されるか
- 入力ファイルなしでの適切なエラーメッセージ

---

## 実装ノート

- JSON 保存は `uv run python -c "import json, datetime; ..."` で行う
- `.cache/pipeline/` ディレクトリが存在しない場合は自動作成する
- `reviewed_at` は UTC ではなくローカル時刻を使用する（`datetime.now().isoformat()`）

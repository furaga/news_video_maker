# /review-video

生成済み動画を人間がレビューし、承認・修正依頼・却下の判定とフィードバックを `.cache/pipeline/05_review.json` に保存する。

## 引数

- 引数なし: インタラクティブにレビューを進める
- `approved`: 承認として即時保存
- `needs_revision <フィードバック>`: 修正依頼として保存
- `rejected <フィードバック>`: 却下として保存

## 実行手順

### ステップ 1: 入力ファイルの読み込み

Read ツールで `.cache/pipeline/04_video_path.txt` を読み込む。
存在しない場合は以下を表示して終了:
```
エラー: .cache/pipeline/04_video_path.txt が見つかりません。
先に /gen-video を実行して動画を生成してください。
```

Read ツールで `.cache/pipeline/03_script.json` を読み込む。
存在しない場合は「台本データなし」として続行する。

### ステップ 2: レビュー情報の表示

以下の形式で表示する:
```
========================================
動画レビュー
========================================
【動画ファイル】
<video_path>

【台本】
Hook: <hook>
本編: <main_narration>
アウトロ: <outro>
タグ: <hashtags>

========================================
上記の動画を再生してレビューしてください。
========================================
```

動画ファイルが存在しない場合は「警告: 動画ファイルが見つかりません」を追加して続行する。

### ステップ 3: 判定の取得

**`$ARGUMENTS` がある場合:**
最初の単語を `status`、残りを `feedback` として使用する。

**`$ARGUMENTS` がない場合:**
ユーザーに確認する:
```
判定を入力してください:
  1. approved        (承認)
  2. needs_revision  (修正依頼)
  3. rejected        (却下)
>
```

### ステップ 4: フィードバックの取得（needs_revision / rejected の場合）

`needs_revision` の場合のみ修正対象を確認する:
```
修正対象を入力（カンマ区切り）: narration / visuals / timing / bgm
>
```

フィードバックコメントを確認する:
```
フィードバックを入力してください:
>
```

### ステップ 5: レビュー結果の保存

以下を `uv run python -c "..."` で実行して保存する:

```python
import json
from datetime import datetime
from pathlib import Path

pipeline_dir = Path(".cache/pipeline")
pipeline_dir.mkdir(parents=True, exist_ok=True)
video_path = Path(".cache/pipeline/04_video_path.txt").read_text().strip()

review = {
    "video_path": video_path,
    "reviewed_at": datetime.now().isoformat(timespec="seconds"),
    "status": "<status>",
    "feedback": "<feedback>",
    "revision_targets": <revision_targets>
}

out = pipeline_dir / "05_review.json"
out.write_text(json.dumps(review, ensure_ascii=False, indent=2))
print(out)
```

`<status>`, `<feedback>`, `<revision_targets>` は実際の値に置き換える。
`revision_targets` は文字列リスト（例: `["narration", "timing"]`）。`approved`/`rejected` は `[]`。

### ステップ 6: 結果サマリの表示

```
========================================
レビュー完了
========================================
動画: <video_path>
判定: <approved=承認✅ / needs_revision=修正依頼🔄 / rejected=却下❌>
日時: <reviewed_at>
フィードバック: <feedback>
<revision_targets がある場合> 修正対象: <revision_targets>

次のステップ:
  approved       → /upload を実行
  needs_revision → /gen-script または /gen-video を実行
  rejected       → /process から記事選定をやり直す
========================================
```

## エラー処理

- `04_video_path.txt` が存在しない → エラーを表示して終了
- `03_script.json` が存在しない → 警告を表示して続行
- 動画ファイルが存在しない → 警告を表示して続行
- 無効な `status` → 再入力を促す

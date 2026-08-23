# /review-video

`review.txt`（またはファイルパスで指定されたファイル）に書かれた人間のレビューを読み、`.cache/pipeline/05_review.json` に保存したうえでフィードバックに応じて修正する。

## 手順

1. レビュー内容を読み込む
   - `review.txt` に直接書かれている場合はそのまま読む
   - ファイルパスが渡された場合はそのファイルの中身を読む

2. レビュー結果を保存する。以下を `uv run python -c "..."` で実行:

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

   - `<status>`, `<feedback>`, `<revision_targets>` は実際の値に置き換える
   - `revision_targets` は文字列リスト（例: `["narration", "timing"]`）。`approved`/`rejected` の場合は `[]`

3. フィードバックに応じて修正する
   - コード修正が必要な場合は worktree を作って作業する（**master から分岐**すること）
   - 複数の異なる種類の修正が必要な場合は、適当な粒度で分割し複数の worktree を作って作業する

4. 修正が終わったら動画を再生成し、結果を確認できるようにする
   - 修正したステージ以降の処理だけ実行すれば十分（例: `03_script` のみ修正した場合、`01_articles`・`02_selected` の工程はスキップ）
   - worktree 内で動画を生成した場合も、このリポジトリ直下の `output/` に保存する（出力先をそこに指定する、または生成後にコピーする）

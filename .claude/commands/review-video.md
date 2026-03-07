# /review-video

生成済み動画を人間がレビューし、フィードバックを与える。
それを `.cache/pipeline/05_review.json` に保存し、フィードバックに応じた修正を行ってください。
フィードバックとしてファイルパスが与えられた場合、そのファイルの中身にレビュー内容が書かれているので参照してください

### レビュー結果の保存

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


### フィードバックに応じた修正

コードの修正を必要とする場合はworktreeを作って、適当な粒度でブランチを切りつつ作業してください。
作業が完了したらPRを出してください
# /review-video

review.txtに人間のレビューが書かれている
それを `.cache/pipeline/05_review.json` に保存し、フィードバックに応じた修正を行ってください。
フィードバックとしてファイルパスが与えられた場合、そのファイルの中身にレビュー内容が書かれているので参照してください

また、修正が終わったら結果を確認できるように動画を再生成してください。修正したステップ以降の処理だけ実行すれば十分です。
例えば、03_scriptの部分だけ修正したら01_articles, 02_selectedの工程はスキップしてください
worktree内で動画を作成した場合であっても、このリポジトリ直下のoutput以下に動画を保存してください（出力先をそこに指定するでも、生成後にコピーするでも構いません）

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

コードの修正を必要とする場合はworktreeを作って作業してください。
複数のことなる種類の修正が必要な場合は、適当な粒度で分割して複数のworktreeを作って作業をしてください
NOTE: ブランチを作るときは、必ずorigin/masterの最新から分岐させてください

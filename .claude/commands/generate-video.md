# /gen-video

`.cache/pipeline/03_script.json` の台本から動画を生成して `output/` に保存する。

## 手順

Bash ツールで以下を実行:

```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.video.composer
```

実行後、生成した動画のパスを報告する。

## 前提条件

- VOICEVOX がローカルで起動していること（http://localhost:50021）
- `.cache/pipeline/03_script.json` が存在すること

## エラー処理

- VOICEVOX 未起動の場合: 「VOICEVOXが起動しているか確認してください」と表示して停止
- moviepy レンダリング失敗: エラーログを表示して停止（中間ファイルは保持）

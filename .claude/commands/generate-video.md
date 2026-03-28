# /gen-video

`.cache/pipeline/03_script.json` の台本から動画を生成して `output/` に保存する。

## 手順

### 1. スクリーンショット撮影・検証

```bash
cd /c/Users/furag/Documents/prog/python/news_video_maker && uv run python -m news_video_maker.video.screenshot
```

撮影に成功した場合、Read ツールで `.cache/images/article_screenshot_full.png`（`PIPELINE_RUN_ID` 設定時は `.cache/images/{run_id}/article_screenshot_full.png`）を読み込み、有効な記事スクリーンショットかを判定する:
- 記事のテキストや画像など、実際のウェブページコンテンツが表示されているか
- 白画面・空白ページ・ブラウザのログイン画面・エラーページではないか

**無効な場合**: 画像ファイルを削除する（composer が SD 生成画像を自動的に hook セクションに使用する）

### 2. 動画生成

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

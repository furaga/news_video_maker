# 実行レポート: 2026-03-07 11:00

## 結果: 一部失敗（動画生成まで成功、YouTube投稿失敗）

## 取得記事数
- 合計: 30件

## 選定記事
- タイトル: Anthropic's Claude found 22 vulnerabilities in Firefox over two weeks
- ソース: techcrunch
- スコア: 9.2

## 生成動画
- パス: output/20260307_105953.mp4
- サイズ: 1.1MB

## YouTube
- ステータス: 失敗
- エラー: `client_secret.json` が見つからない（`.env` の `YOUTUBE_CLIENT_SECRET_PATH` を確認してください）

## エラー
- ステージ5（YouTube投稿）: `FileNotFoundError: クライアントシークレットが見つかりません: client_secret.json`
- 対処: `.env` に `YOUTUBE_CLIENT_SECRET_PATH` を正しく設定し、Google Cloud Console から OAuth 2.0 クライアントシークレットをダウンロードしてください
- 再実行: `--from-stage 5` で YouTube 投稿のみ再実行可能

"""パイプライン実行エントリーポイント"""
import argparse
import sys
from datetime import datetime, timedelta, timezone

import anyio

from news_video_maker.pipeline import run

_JST = timezone(timedelta(hours=9))


def _parse_publish_at(publish_time: str) -> str:
    """HH:MM (JST) を翌日同時刻の ISO 8601 UTC 文字列に変換"""
    hour, minute = map(int, publish_time.split(":"))
    now_jst = datetime.now(_JST)
    tomorrow_jst = (now_jst + timedelta(days=1)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    return tomorrow_jst.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    parser = argparse.ArgumentParser(
        description="ニュース動画自動生成・YouTube投稿パイプライン"
    )
    parser.add_argument(
        "--dry-run",
        "--skip-upload",
        action="store_true",
        help="動画生成まで実行し、YouTube投稿をスキップ",
    )
    parser.add_argument(
        "--from-stage",
        type=int,
        default=1,
        choices=[1, 2, 3, 4, 5],
        metavar="N",
        help="ステージ N から再開 (1=fetch, 2=process, 3=script, 4=video, 5=upload)",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="実行ID（省略時は自動生成。複数同時実行時に明示指定するとキャッシュが分離される）",
    )
    parser.add_argument(
        "--publish-time",
        default="",
        metavar="HH:MM",
        help="YouTube 公開スケジュール時刻（JST）。例: 8:00 → 翌日 08:00 JST に公開予約",
    )
    parser.add_argument(
        "--mode",
        default="news",
        choices=["news", "paper", "trivia", "space"],
        help="実行モード（news: テックニュース, paper: 論文, trivia: 雑学, space: 宇宙）",
    )
    args = parser.parse_args()

    publish_at = _parse_publish_at(args.publish_time) if args.publish_time else ""
    exit_code = anyio.run(run, args.dry_run, args.from_stage, args.run_id, publish_at, args.mode)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

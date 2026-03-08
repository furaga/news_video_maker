"""パイプライン実行エントリーポイント"""
import argparse
import sys

import anyio

from news_video_maker.pipeline import run


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
    args = parser.parse_args()

    exit_code = anyio.run(run, args.dry_run, args.from_stage, args.run_id)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

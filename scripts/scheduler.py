"""スケジューラー: 指定時刻スロットに動画が予約済みかチェックし、不足分を生成・投稿する"""
import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from news_video_maker.config import YOUTUBE_CLIENT_SECRET_PATH, YOUTUBE_TOKEN_PATH

_JST = timezone(timedelta(hours=9))
_UTC = timezone.utc

# スケジューラー専用トークン（youtube.readonly スコープ）
# uploader の token.json（youtube.upload スコープ）とは別ファイルで管理する
_SCHEDULER_TOKEN_PATH = YOUTUBE_TOKEN_PATH.parent / "scheduler_token.json"
_SCHEDULER_SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# --- YouTube 認証 -----------------------------------------------------------

def _get_youtube_service():
    """OAuth 2.0 認証済み YouTube サービスを返す（スケジューラー専用トークン）"""
    import google.auth.transport.requests

    creds = None
    if _SCHEDULER_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(
            str(_SCHEDULER_TOKEN_PATH), _SCHEDULER_SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            if not YOUTUBE_CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(
                    f"クライアントシークレットが見つかりません: {YOUTUBE_CLIENT_SECRET_PATH}\n"
                    ".env の YOUTUBE_CLIENT_SECRET_PATH を確認してください。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(YOUTUBE_CLIENT_SECRET_PATH), _SCHEDULER_SCOPES
            )
            creds = flow.run_local_server(port=0)

        _SCHEDULER_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        logger.info("スケジューラートークンを保存しました: %s", _SCHEDULER_TOKEN_PATH)

    return build("youtube", "v3", credentials=creds)


# --- スケジュール確認 ---------------------------------------------------------

def _get_scheduled_publish_times(youtube) -> list[datetime]:
    """チャンネルにスケジュール済みのprivate動画のpublishAt一覧を返す（UTC datetime）"""
    # アップロードプレイリスト ID を取得
    ch_resp = youtube.channels().list(part="contentDetails", mine=True).execute()
    items = ch_resp.get("items", [])
    if not items:
        logger.warning("チャンネル情報を取得できませんでした")
        return []
    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # 最新50件の動画IDを取得
    pl_resp = youtube.playlistItems().list(
        part="snippet",
        playlistId=uploads_id,
        maxResults=50,
    ).execute()
    video_ids = [
        item["snippet"]["resourceId"]["videoId"]
        for item in pl_resp.get("items", [])
    ]
    if not video_ids:
        return []

    # status.publishAt を取得
    vid_resp = youtube.videos().list(
        part="status",
        id=",".join(video_ids),
    ).execute()

    result = []
    for item in vid_resp.get("items", []):
        status = item.get("status", {})
        if status.get("privacyStatus") == "private" and status.get("publishAt"):
            dt = datetime.fromisoformat(status["publishAt"].replace("Z", "+00:00"))
            result.append(dt.astimezone(_UTC))
    return result


# --- スロット計算 -------------------------------------------------------------

def _build_target_slots(publish_times: list[str], days_ahead: int) -> list[datetime]:
    """今日からdays_ahead日分のターゲットスロット（UTC datetime）を返す"""
    slots = []
    today_jst = datetime.now(_JST).date()
    for day_offset in range(days_ahead):
        date = today_jst + timedelta(days=day_offset)
        for t in publish_times:
            hour, minute = map(int, t.split(":"))
            slot_jst = datetime(date.year, date.month, date.day, hour, minute, tzinfo=_JST)
            slots.append(slot_jst.astimezone(_UTC))
    return slots


def _find_missing_slots(
    target_slots: list[datetime],
    scheduled: list[datetime],
    tolerance_minutes: int = 10,
) -> list[datetime]:
    """スケジュール済みリストにないターゲットスロットを返す（過去スロットはスキップ）"""
    now_utc = datetime.now(_UTC)
    missing = []
    for slot in target_slots:
        if slot <= now_utc:
            continue  # 過去または現在は不要
        matched = any(
            abs((slot - s).total_seconds()) <= tolerance_minutes * 60
            for s in scheduled
        )
        if not matched:
            missing.append(slot)
    return missing


# --- パイプライン実行 ---------------------------------------------------------

def _run_pipeline_for_slot(slot_utc: datetime, mode: str, dry_run: bool) -> None:
    """欠落スロットに対してパイプラインを実行する"""
    publish_at = slot_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    slot_jst = slot_utc.astimezone(_JST).strftime("%Y-%m-%d %H:%M JST")
    logger.info("動画生成開始: %s → publish_at=%s", slot_jst, publish_at)

    cmd = [
        "uv", "run", "python",
        str(PROJECT_DIR / "scripts" / "run_pipeline.py"),
        "--publish-at", publish_at,
        "--mode", mode,
    ]
    if dry_run:
        cmd.append("--dry-run")

    logger.info("コマンド: %s", " ".join(cmd))
    if dry_run:
        logger.info("[dry-run] 実際には実行しません")
        return

    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))
    if result.returncode != 0:
        logger.error("パイプライン失敗 (returncode=%d): %s", result.returncode, slot_jst)


# --- メインロジック -----------------------------------------------------------

def check_and_fill(config: dict, dry_run: bool) -> None:
    """一回分のチェックと補完を実行する"""
    sched_cfg = config["schedule"]
    publish_times: list[str] = sched_cfg["publish_times"]
    days_ahead: int = sched_cfg.get("days_ahead", 3)
    mode: str = sched_cfg.get("mode", "news")

    youtube = _get_youtube_service()
    scheduled = _get_scheduled_publish_times(youtube)
    logger.info("スケジュール済み動画: %d件", len(scheduled))
    for s in scheduled:
        logger.info("  - %s", s.astimezone(_JST).strftime("%Y-%m-%d %H:%M JST"))

    target_slots = _build_target_slots(publish_times, days_ahead)
    missing = _find_missing_slots(target_slots, scheduled)
    logger.info("未スケジュールスロット: %d件", len(missing))
    for m in missing:
        logger.info("  - %s", m.astimezone(_JST).strftime("%Y-%m-%d %H:%M JST"))

    for slot in missing:
        _run_pipeline_for_slot(slot, mode, dry_run)


def main():
    parser = argparse.ArgumentParser(
        description="YouTube スケジュール補完スクリプト"
    )
    parser.add_argument(
        "--config",
        default="config/schedule.yml",
        help="設定ファイルパス（デフォルト: config/schedule.yml）",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="1回チェックして終了（省略時は --daemon と同じ動作）",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="check_interval_minutes ごとに定期チェックするループモード",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="パイプラインを実際に実行せず、確認のみ行う",
    )
    args = parser.parse_args()

    config_path = PROJECT_DIR / args.config
    if not config_path.exists():
        logger.error("設定ファイルが見つかりません: %s", config_path)
        sys.exit(1)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    interval_minutes: int = config.get("scheduler", {}).get("check_interval_minutes", 60)

    if args.once or not args.daemon:
        check_and_fill(config, args.dry_run)
    else:
        logger.info("daemonモード開始 (interval=%d分)", interval_minutes)
        while True:
            try:
                check_and_fill(config, args.dry_run)
            except Exception as e:
                logger.error("チェック中にエラーが発生しました: %s", e, exc_info=True)
            logger.info("%d分後に再チェックします...", interval_minutes)
            time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    main()

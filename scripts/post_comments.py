"""過去動画に投稿者コメントを一括投稿するスクリプト

対象: 非公開・スケジュール公開動画のみ（公開・限定公開はスキップ）

ワークアラウンド: YouTube API はコメント投稿を公開/限定公開動画のみ許可するため、
非公開・スケジュール動画を一時的に限定公開→コメント投稿→元の状態に戻す。

使い方:
    uv run python scripts/post_comments.py --video-id VIDEO_ID           # 投稿
    uv run python scripts/post_comments.py --video-id VIDEO_ID --dry-run # 確認のみ
"""
import argparse
import logging
import os
import re
from pathlib import Path

import google.auth.transport.requests
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
TOKEN_PATH = BASE_DIR / "token_comment.json"
CLIENT_SECRET_PATH = Path(os.getenv("YOUTUBE_CLIENT_SECRET_PATH", "./client_secret.json"))
COMMENTS_FILE = BASE_DIR / ".cache" / "youtube_comments.md"


def parse_comments_file(path: Path) -> list[tuple[str, str]]:
    """youtube_comments.md をパースして (video_id, comment_text) のリストを返す。
    URL が「（未アップロード）」の項目はスキップ。"""
    text = path.read_text(encoding="utf-8")
    results = []

    # セクション区切りは "---" 行
    # 各セクション: ## タイトル / URL行 / 生成日行 / 本文
    sections = re.split(r"\n---\n", text)
    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue

        video_id = None
        comment_lines = []
        in_body = False

        for line in lines:
            url_match = re.match(r"URL:\s+https://youtu\.be/(\S+)", line)
            if url_match:
                video_id = url_match.group(1)
                in_body = False
                continue
            if line.startswith("URL:") and "未アップロード" in line:
                video_id = None
                break
            if line.startswith("## ") or line.startswith("生成日:") or line.startswith("# "):
                continue
            if video_id is not None:
                in_body = True
            if in_body and line:
                comment_lines.append(line)

        if video_id and comment_lines:
            results.append((video_id, "\n".join(comment_lines).strip()))

    return results


def authenticate():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(f"クライアントシークレットが見つかりません: {CLIENT_SECRET_PATH}")
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        logger.info("認証トークンを保存しました: %s", TOKEN_PATH)

    return build("youtube", "v3", credentials=creds)


def get_video_status(youtube, video_ids: list[str]) -> dict[str, dict]:
    """video_id → {"privacyStatus": str, "publishAt": str | None} の辞書を返す"""
    response = youtube.videos().list(
        part="status",
        id=",".join(video_ids),
    ).execute()
    result = {}
    for item in response.get("items", []):
        status = item["status"]
        result[item["id"]] = {
            "privacyStatus": status.get("privacyStatus"),
            "publishAt": status.get("publishAt"),
        }
    return result


def set_video_status(youtube, video_id: str, privacy: str, publish_at: str | None = None):
    """動画のプライバシー状態を変更する"""
    status_body: dict = {"privacyStatus": privacy}
    if publish_at:
        status_body["publishAt"] = publish_at
    youtube.videos().update(
        part="status",
        body={"id": video_id, "status": status_body},
    ).execute()


def post_comment(youtube, video_id: str, text: str) -> str:
    response = youtube.commentThreads().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {
                    "snippet": {"textOriginal": text}
                },
            }
        },
    ).execute()
    return response["id"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="投稿せず確認のみ")
    parser.add_argument("--video-id", required=True, help="対象動画ID（必須）")
    args = parser.parse_args()

    if not COMMENTS_FILE.exists():
        print(f"コメントファイルが見つかりません: {COMMENTS_FILE}")
        return

    comments = parse_comments_file(COMMENTS_FILE)
    comments = [(vid, text) for vid, text in comments if vid == args.video_id]
    if not comments:
        print(f"指定された動画IDのコメントが見つかりません: {args.video_id}")
        return

    youtube = authenticate()

    video_id, text = comments[0]
    url = f"https://youtu.be/{video_id}"
    s = get_video_status(youtube, [video_id]).get(video_id, {})
    privacy = s.get("privacyStatus")
    publish_at = s.get("publishAt")
    label = f"スケジュール({publish_at})" if publish_at else privacy or "不明"

    if privacy != "private":
        print(f"スキップ: {url} ({privacy}) — 非公開・スケジュール動画のみ対象")
        return

    if args.dry_run:
        print(f"=== DRY RUN ===\n[{label}] {url}")
        print(text[:80] + "...")
        return

    try:
        logger.info("限定公開に変更中: %s (%s)", url, label)
        set_video_status(youtube, video_id, "unlisted")
        try:
            comment_id = post_comment(youtube, video_id, text)
            logger.info("コメント投稿完了: %s → comment_id: %s", url, comment_id)
        finally:
            logger.info("元の状態に復元中: %s", url)
            set_video_status(youtube, video_id, "private", publish_at)
    except HttpError as e:
        logger.error("失敗 %s: %s", url, e)


if __name__ == "__main__":
    main()

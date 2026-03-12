"""過去動画に投稿者コメントを一括投稿するスクリプト

対象: 非公開・スケジュール公開動画のみ（公開・限定公開はスキップ）

ワークアラウンド: YouTube API はコメント投稿を公開/限定公開動画のみ許可するため、
非公開・スケジュール動画を一時的に限定公開→コメント投稿→元の状態に戻す。

使い方:
    uv run python scripts/post_comments.py
    uv run python scripts/post_comments.py --dry-run  # 投稿せず確認のみ
"""
import argparse
import logging
import os
import re
import time
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
    args = parser.parse_args()

    if not COMMENTS_FILE.exists():
        print(f"コメントファイルが見つかりません: {COMMENTS_FILE}")
        return

    comments = parse_comments_file(COMMENTS_FILE)
    if not comments:
        print("コメント対象の動画が見つかりません。")
        return

    youtube = authenticate()

    all_video_ids = [vid for vid, _ in comments]
    status_map = get_video_status(youtube, all_video_ids)

    # 非公開・スケジュールのみ対象
    targets = []
    skipped = []
    for vid, text in comments:
        s = status_map.get(vid, {})
        privacy = s.get("privacyStatus")
        if privacy == "private":
            targets.append((vid, text, s.get("publishAt")))
        else:
            skipped.append((vid, privacy or "不明"))

    print(f"対象（非公開・スケジュール）: {len(targets)} 件 / スキップ: {len(skipped)} 件\n")
    for vid, reason in skipped:
        print(f"  スキップ: https://youtu.be/{vid} ({reason})")

    if args.dry_run:
        print(f"\n=== DRY RUN: {len(targets)} 件を投稿予定 ===")
        for vid, text, publish_at in targets:
            label = f"スケジュール({publish_at})" if publish_at else "非公開"
            print(f"\n[{label}] https://youtu.be/{vid}")
            print(text[:80] + "...")
        return

    if not targets:
        print("\n投稿対象の動画がありません。")
        return

    print()
    success = 0
    for i, (video_id, text, publish_at) in enumerate(targets, 1):
        url = f"https://youtu.be/{video_id}"
        label = f"スケジュール({publish_at})" if publish_at else "非公開"
        try:
            logger.info("[%d/%d] 限定公開に変更中: %s (%s)", i, len(targets), url, label)
            set_video_status(youtube, video_id, "unlisted")
            try:
                comment_id = post_comment(youtube, video_id, text)
                logger.info("[%d/%d] コメント投稿完了: %s → comment_id: %s", i, len(targets), url, comment_id)
                success += 1
            finally:
                # コメント失敗時も必ず元の状態に戻す
                logger.info("[%d/%d] 元の状態に復元中: %s", i, len(targets), url)
                set_video_status(youtube, video_id, "private", publish_at)
        except HttpError as e:
            logger.error("[%d/%d] 失敗 %s: %s", i, len(targets), url, e)
        if i < len(targets):
            time.sleep(2)

    print(f"\n完了: {success}/{len(targets)} 件投稿しました。{len(skipped)} 件はスキップ（公開・限定公開）。")


if __name__ == "__main__":
    main()

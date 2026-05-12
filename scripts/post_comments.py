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


def update_comments_file_url(path: Path, video_id: str, comment_text: str) -> bool:
    """youtube_comments.md の（未アップロード）エントリを実URLに更新する。
    comment_text の先頭40文字でマッチングする。"""
    if not path.exists():
        return False

    full_text = path.read_text(encoding="utf-8")
    sections = full_text.split("\n---\n")
    updated = False
    snippet = comment_text.strip()[:40]

    for i, section in enumerate(sections):
        if "未アップロード" not in section:
            continue
        if snippet and snippet in section:
            sections[i] = section.replace(
                "URL: （未アップロード）",
                f"URL: https://youtu.be/{video_id}",
            )
            updated = True
            break

    if updated:
        path.write_text("\n---\n".join(sections), encoding="utf-8")
        logger.info("youtube_comments.md を更新: %s → https://youtu.be/%s", snippet[:20], video_id)
    return updated


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
    parser.add_argument("--comment-file", type=str, default=None,
                        help="コメントテキストファイルのパス（指定時はyoutube_comments.mdの検索をスキップ）")
    args = parser.parse_args()

    video_id = args.video_id

    # コメント本文を解決
    if args.comment_file:
        comment_path = Path(args.comment_file)
        if not comment_path.exists():
            print(f"コメントファイルが見つかりません: {comment_path}")
            return
        text = comment_path.read_text(encoding="utf-8").strip()
        if not text:
            print(f"コメントファイルが空です: {comment_path}")
            return
    else:
        if not COMMENTS_FILE.exists():
            print(f"コメントファイルが見つかりません: {COMMENTS_FILE}")
            return
        comments = parse_comments_file(COMMENTS_FILE)
        comments = [(vid, t) for vid, t in comments if vid == video_id]
        if not comments:
            print(f"指定された動画IDのコメントが見つかりません: {video_id}")
            return
        _, text = comments[0]

    youtube = authenticate()

    url = f"https://youtu.be/{video_id}"

    # 動画ステータス確認（リトライ付き: アップロード直後のAPI反映遅延に対応）
    privacy = None
    publish_at = None
    for attempt in range(3):
        s = get_video_status(youtube, [video_id]).get(video_id, {})
        privacy = s.get("privacyStatus")
        publish_at = s.get("publishAt")
        if privacy == "private":
            break
        if attempt < 2:
            logger.info("動画ステータス確認待ち (%s)... 10秒後にリトライ", privacy)
            time.sleep(10)
    else:
        label = f"スケジュール({publish_at})" if publish_at else privacy or "不明"
        print(f"スキップ: {url} ({label}) — 非公開・スケジュール動画のみ対象")
        return

    label = f"スケジュール({publish_at})" if publish_at else "private"

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
            # youtube_comments.md の（未アップロード）エントリを自動更新
            if COMMENTS_FILE.exists():
                update_comments_file_url(COMMENTS_FILE, video_id, text)
        finally:
            logger.info("元の状態に復元中: %s", url)
            set_video_status(youtube, video_id, "private", publish_at)
    except HttpError as e:
        logger.error("失敗 %s: %s", url, e)


if __name__ == "__main__":
    main()

"""YouTube Data API v3 アップロード"""
import json
import logging
import time
from pathlib import Path

import httplib2
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from news_video_maker.config import (
    CHANNEL_DESCRIPTION_FOOTER,
    CHANNEL_HASHTAGS,
    PIPELINE_DIR,
    YOUTUBE_CLIENT_SECRET_PATH,
    YOUTUBE_PRIVACY,
    YOUTUBE_SCOPES,
    YOUTUBE_TOKEN_PATH,
)
from news_video_maker.history import HistoryStore

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def _authenticate():
    """OAuth 2.0 認証。token.json があれば再利用、なければブラウザで認証"""
    import google.auth.transport.requests
    from google.oauth2.credentials import Credentials

    creds = None
    if YOUTUBE_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(YOUTUBE_TOKEN_PATH), YOUTUBE_SCOPES)

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
                str(YOUTUBE_CLIENT_SECRET_PATH), YOUTUBE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        YOUTUBE_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        logger.info("認証トークンを保存しました: %s", YOUTUBE_TOKEN_PATH)

    return build("youtube", "v3", credentials=creds)


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy: str = YOUTUBE_PRIVACY,
) -> str:
    """動画をアップロードして YouTube URL を返す"""
    if not video_path.exists():
        raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

    youtube = _authenticate()

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "28",  # Science & Technology
            "defaultLanguage": "ja",
        },
        "status": {
            "privacyStatus": privacy,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    # リトライ付きアップロード
    response = None
    wait = 10
    for attempt in range(MAX_RETRIES):
        try:
            logger.info("アップロード中... (試行 %d/%d)", attempt + 1, MAX_RETRIES)
            status, response = request.next_chunk()
            while response is None:
                status, response = request.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    print(f"\rアップロード中: {pct}%", end="", flush=True)
            print()
            break
        except HttpError as e:
            if e.resp.status in (403,) and b"quotaExceeded" in e.content:
                raise RuntimeError(
                    "YouTube API のクォータ上限に達しました。翌日以降に再試行してください。"
                ) from e
            if attempt < MAX_RETRIES - 1:
                logger.warning("アップロード失敗 (試行 %d): %s", attempt + 1, e)
                time.sleep(wait)
                wait *= 2
            else:
                raise

    video_id = response["id"]
    url = f"https://youtu.be/{video_id}"
    logger.info("アップロード完了: %s", url)
    return url


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # 入力ファイル読み込み
    path_file = PIPELINE_DIR / "04_video_path.txt"
    if not path_file.exists():
        raise FileNotFoundError(f"動画パスファイルが見つかりません: {path_file}")

    video_path = Path(path_file.read_text(encoding="utf-8").strip())

    selected_path = PIPELINE_DIR / "02_selected.json"
    script_path = PIPELINE_DIR / "03_script.json"

    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    script = json.loads(script_path.read_text(encoding="utf-8"))

    title = script.get("title", selected.get("japanese_title", "テックニュース"))
    source = selected.get("source", "")
    source_url = selected.get("url", "")
    summary = selected.get("japanese_summary", "")

    # 05_metadata.json があれば優先使用、なければフォールバック
    metadata_path = PIPELINE_DIR / "05_metadata.json"
    try:
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            description = metadata["description"]
            tags = metadata["tags"]
            logger.info("05_metadata.json からメタデータを読み込みました")
        else:
            raise FileNotFoundError("05_metadata.json が存在しません")
    except Exception as e:
        logger.warning("メタデータ読み込み失敗。フォールバックを使用します: %s", e)
        description = (
            f"{summary}\n\n"
            f"元記事: {source_url}\n\n"
            "---\n"
            f"{CHANNEL_DESCRIPTION_FOOTER}\n\n"
            f"{CHANNEL_HASHTAGS}"
        )
        tags = [t.lstrip("#") for t in CHANNEL_HASHTAGS.split()] + [source]

    url = upload_video(video_path, title, description, tags)

    # URL保存
    url_file = PIPELINE_DIR / "05_youtube_url.txt"
    url_file.write_text(url, encoding="utf-8")
    print(f"YouTube URL: {url}")

    # 履歴に記録
    try:
        HistoryStore().record(url=source_url, title=title, source=source, youtube_url=url)
    except Exception as e:
        logger.warning("履歴記録失敗: %s", e)


if __name__ == "__main__":
    main()

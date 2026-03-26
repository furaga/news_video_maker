"""BGM URL からキャッシュ済みファイルパスを返す。初回のみダウンロードする。"""
import hashlib
import logging
from pathlib import Path

import httpx

from news_video_maker.config import BGM_CACHE_DIR

logger = logging.getLogger(__name__)


def get_bgm_path(bgm_url: str) -> Path | None:
    """bgm_url が空の場合は None を返す。
    キャッシュ済みの場合はそのパスを返す。
    未キャッシュの場合はダウンロードしてパスを返す。
    ダウンロード失敗時は None を返す（パイプラインを停止しない）。
    """
    if not bgm_url:
        return None

    url_hash = hashlib.sha256(bgm_url.encode()).hexdigest()[:16]
    # URL の拡張子を保持（.mp3 / .wav / .ogg など）
    url_path = bgm_url.split("?")[0]  # クエリパラメータを除去
    ext = Path(url_path).suffix or ".mp3"
    cache_path = BGM_CACHE_DIR / f"{url_hash}{ext}"

    if cache_path.exists():
        logger.info("BGMキャッシュ使用: %s", cache_path.name)
        return cache_path

    logger.info("BGMダウンロード開始: %s", bgm_url)
    try:
        BGM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            response = client.get(bgm_url)
            response.raise_for_status()
        cache_path.write_bytes(response.content)
        logger.info("BGMダウンロード完了: %s (%d bytes)", cache_path.name, len(response.content))
        return cache_path
    except Exception as e:
        logger.warning("BGMダウンロード失敗（BGMなしで続行）: %s", e)
        return None
